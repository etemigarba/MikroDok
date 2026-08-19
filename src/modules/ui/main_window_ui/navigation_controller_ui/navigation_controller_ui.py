"""
Module: navigation_controller_ui
Description: Manages navigation between different application views and maintains navigation history
            for MikroDok application. Provides comprehensive view management, routing, navigation state
            tracking, and seamless integration with the app shell. Implements modern navigation patterns
            with responsive design and full theme system integration.
Phase: 1
Location: /src/modules/ui/main_window_ui/navigation_controller_ui/navigation_controller_ui.py
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
    get_theme_manager,
    ScreenSize
)

# Configure logging
logger = logging.getLogger(__name__)


class NavigationState(Enum):
    """Navigation state enumeration."""
    IDLE = "idle"
    NAVIGATING = "navigating"
    LOADING = "loading"
    ERROR = "error"


class ViewTransitionType(Enum):
    """View transition type enumeration."""
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    FADE = "fade"
    SCALE = "scale"
    NONE = "none"


@dataclass
class NavigationRoute:
    """Navigation route configuration."""
    route_id: str
    path: str
    title: str
    icon: str
    view_factory: Optional[Callable] = None
    requires_auth: bool = False
    is_modal: bool = False
    transition: ViewTransitionType = ViewTransitionType.FADE
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_route: Optional[str] = None
    children: List[str] = field(default_factory=list)


@dataclass
class NavigationHistoryEntry:
    """Navigation history entry."""
    route_id: str
    path: str
    title: str
    timestamp: datetime
    state_data: Dict[str, Any] = field(default_factory=dict)
    scroll_position: Tuple[float, float] = (0, 0)


@dataclass
class BreadcrumbItem:
    """Breadcrumb navigation item."""
    route_id: str
    title: str
    path: str
    is_clickable: bool = True


class NavigationControllerUI(ThemeAwareUserControl):
    """
    Navigation controller for managing application views and navigation state.
    
    Features:
    - Comprehensive view management and routing
    - Navigation history with back/forward support
    - Breadcrumb navigation tracking
    - View transition animations
    - State persistence and restoration
    - Error handling and recovery
    - Full theme system integration with responsive design
    - Performance-optimized view loading
    - Accessibility-compliant navigation
    - Modern UI/UX with elegant transitions
    """

    def __init__(
        self,
        initial_route: str = "/dashboard",
        enable_history: bool = True,
        max_history_size: int = 50,
        enable_transitions: bool = True,
        on_navigation_change: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        
        # Configuration
        self._initial_route = initial_route
        self._enable_history = enable_history
        self._max_history_size = max_history_size
        self._enable_transitions = enable_transitions
        self._on_navigation_change = on_navigation_change
        
        # State management
        self._current_route: Optional[NavigationRoute] = None
        self._current_view: Optional[ft.Control] = None
        self._navigation_state = NavigationState.IDLE
        self._routes: Dict[str, NavigationRoute] = {}
        self._history: List[NavigationHistoryEntry] = []
        self._history_index = -1
        self._breadcrumbs: List[BreadcrumbItem] = []
        
        # View management
        self._view_cache: Dict[str, ft.Control] = {}
        self._view_factories: Dict[str, Callable] = {}
        self._loading_views: Dict[str, bool] = {}
        
        # UI components
        self._content_container: Optional[ft.Container] = None
        self._loading_overlay: Optional[ft.Container] = None
        self._error_view: Optional[ft.Container] = None
        
        # Callbacks and observers
        self._route_change_callbacks: List[Callable] = []
        self._view_load_callbacks: List[Callable] = []
        self._error_callbacks: List[Callable] = []
        
        # Initialize default routes
        self._initialize_default_routes()
        
        logger.debug("NavigationControllerUI initialized")

    def build(self) -> ft.Control:
        """Build the navigation controller UI."""
        try:
            self._ensure_theme_manager()
            palette = self.get_palette()
            spacing = self.get_spacing()
            
            # Create main content container
            self._content_container = self.create_responsive_container(
                content=self._build_default_view(),
                bgcolor=palette.surface,
                border_radius=self.get_breakpoint_value(0, 4, 8, 12),
                padding=0,
                margin=0,
                expand=True
            )
            
            # Create loading overlay
            self._loading_overlay = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.ProgressRing(
                            width=self.get_breakpoint_value(32, 40, 48, 56),
                            height=self.get_breakpoint_value(32, 40, 48, 56),
                            color=palette.primary
                        ),
                        ft.Text(
                            "Loading...",
                            style=self.get_text_style("bodyMedium"),
                            color=palette.on_surface,
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=spacing.md
                ),
                bgcolor=palette.surface_variant,
                border_radius=self.get_breakpoint_value(8, 12, 16, 20),
                padding=spacing.xl,
                alignment=ft.alignment.center,
                visible=False
            )
            
            # Create main layout
            return ft.Stack(
                controls=[
                    self._content_container,
                    self._loading_overlay
                ],
                expand=True
            )
            
        except Exception as e:
            logger.error(f"Error building navigation controller: {e}")
            return self._build_error_fallback()

    def _build_default_view(self) -> ft.Control:
        """Build the default view when no route is loaded."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        name=ft.Icons.NAVIGATION,
                        size=self.get_breakpoint_value(64, 80, 96, 128),
                        color=palette.primary
                    ),
                    ft.Text(
                        "Navigation Controller",
                        style=self.get_text_style("headlineMedium"),
                        color=palette.on_surface,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        "Ready to navigate",
                        style=self.get_text_style("bodyLarge"),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.lg
            ),
            alignment=ft.alignment.center,
            expand=True
        )

    def _build_error_fallback(self) -> ft.Control:
        """Build error fallback view."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        name=ft.Icons.ERROR_OUTLINE,
                        size=self.get_breakpoint_value(48, 56, 64, 72),
                        color=palette.error
                    ),
                    ft.Text(
                        "Navigation Error",
                        style=self.get_text_style("headlineSmall"),
                        color=palette.error,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        "Unable to load navigation controller",
                        style=self.get_text_style("bodyMedium"),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.md
            ),
            alignment=ft.alignment.center,
            expand=True
        )

    def _initialize_default_routes(self):
        """Initialize default application routes."""
        try:
            default_routes = [
                NavigationRoute(
                    route_id="dashboard",
                    path="/dashboard",
                    title="Dashboard",
                    icon=ft.Icons.DASHBOARD,
                    transition=ViewTransitionType.FADE
                ),
                NavigationRoute(
                    route_id="documents",
                    path="/documents",
                    title="Documents",
                    icon=ft.Icons.DESCRIPTION,
                    transition=ViewTransitionType.SLIDE_LEFT
                ),
                NavigationRoute(
                    route_id="models",
                    path="/models",
                    title="Models",
                    icon=ft.Icons.PSYCHOLOGY,
                    transition=ViewTransitionType.SLIDE_LEFT
                ),
                NavigationRoute(
                    route_id="training",
                    path="/training",
                    title="Training",
                    icon=ft.Icons.FITNESS_CENTER,
                    transition=ViewTransitionType.SLIDE_LEFT
                ),
                NavigationRoute(
                    route_id="settings",
                    path="/settings",
                    title="Settings",
                    icon=ft.Icons.SETTINGS,
                    transition=ViewTransitionType.FADE
                )
            ]
            
            for route in default_routes:
                self._routes[route.route_id] = route
                
            logger.debug(f"Initialized {len(default_routes)} default routes")
            
        except Exception as e:
            logger.error(f"Error initializing default routes: {e}")

    # Route Management Methods
    def register_route(self, route: NavigationRoute) -> bool:
        """
        Register a new navigation route.

        Args:
            route: Navigation route to register

        Returns:
            True if route was registered successfully
        """
        try:
            self._routes[route.route_id] = route
            logger.debug(f"Route registered: {route.route_id}")
            return True
        except Exception as e:
            logger.error(f"Error registering route {route.route_id}: {e}")
            return False

    def unregister_route(self, route_id: str) -> bool:
        """
        Unregister a navigation route.

        Args:
            route_id: ID of route to unregister

        Returns:
            True if route was unregistered successfully
        """
        try:
            if route_id in self._routes:
                del self._routes[route_id]
                # Clear from cache if present
                if route_id in self._view_cache:
                    del self._view_cache[route_id]
                logger.debug(f"Route unregistered: {route_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error unregistering route {route_id}: {e}")
            return False

    def register_view_factory(self, route_id: str, factory: Callable) -> bool:
        """
        Register a view factory for a route.

        Args:
            route_id: Route ID
            factory: Factory function that creates the view

        Returns:
            True if factory was registered successfully
        """
        try:
            self._view_factories[route_id] = factory
            if route_id in self._routes:
                self._routes[route_id].view_factory = factory
            logger.debug(f"View factory registered for route: {route_id}")
            return True
        except Exception as e:
            logger.error(f"Error registering view factory for {route_id}: {e}")
            return False

    # Navigation Methods
    async def navigate_to(
        self,
        route_id: str,
        state_data: Optional[Dict[str, Any]] = None,
        force_reload: bool = False
    ) -> bool:
        """
        Navigate to a specific route.

        Args:
            route_id: ID of route to navigate to
            state_data: Optional state data to pass to the view
            force_reload: Force reload of the view even if cached

        Returns:
            True if navigation was successful
        """
        try:
            if route_id not in self._routes:
                logger.error(f"Route not found: {route_id}")
                return False

            route = self._routes[route_id]

            # Update navigation state
            self._navigation_state = NavigationState.NAVIGATING
            self._show_loading(True)

            # Add to history if enabled
            if self._enable_history and self._current_route:
                self._add_to_history(self._current_route, state_data or {})

            # Load the view
            view = await self._load_view(route, force_reload)
            if view is None:
                self._navigation_state = NavigationState.ERROR
                self._show_loading(False)
                return False

            # Update current state
            self._current_route = route
            self._current_view = view
            self._navigation_state = NavigationState.IDLE

            # Update UI
            self._update_content_view(view)
            self._update_breadcrumbs()
            self._show_loading(False)

            # Notify callbacks
            self._notify_route_change_callbacks(route, state_data)

            logger.debug(f"Navigation completed to: {route_id}")
            return True

        except Exception as e:
            logger.error(f"Error navigating to {route_id}: {e}")
            self._navigation_state = NavigationState.ERROR
            self._show_loading(False)
            return False

    async def navigate_back(self) -> bool:
        """
        Navigate back in history.

        Returns:
            True if navigation was successful
        """
        try:
            if not self._enable_history or self._history_index <= 0:
                return False

            self._history_index -= 1
            entry = self._history[self._history_index]

            return await self.navigate_to(entry.route_id, entry.state_data)

        except Exception as e:
            logger.error(f"Error navigating back: {e}")
            return False

    async def navigate_forward(self) -> bool:
        """
        Navigate forward in history.

        Returns:
            True if navigation was successful
        """
        try:
            if not self._enable_history or self._history_index >= len(self._history) - 1:
                return False

            self._history_index += 1
            entry = self._history[self._history_index]

            return await self.navigate_to(entry.route_id, entry.state_data)

        except Exception as e:
            logger.error(f"Error navigating forward: {e}")
            return False

    def can_navigate_back(self) -> bool:
        """Check if back navigation is possible."""
        return self._enable_history and self._history_index > 0

    def can_navigate_forward(self) -> bool:
        """Check if forward navigation is possible."""
        return self._enable_history and self._history_index < len(self._history) - 1

    async def _load_view(self, route: NavigationRoute, force_reload: bool = False) -> Optional[ft.Control]:
        """
        Load a view for the given route.

        Args:
            route: Navigation route
            force_reload: Force reload even if cached

        Returns:
            Loaded view control or None if failed
        """
        try:
            # Check cache first
            if not force_reload and route.route_id in self._view_cache:
                logger.debug(f"Loading view from cache: {route.route_id}")
                return self._view_cache[route.route_id]

            # Check if already loading
            if route.route_id in self._loading_views:
                logger.debug(f"View already loading: {route.route_id}")
                return None

            self._loading_views[route.route_id] = True

            try:
                # Use factory if available
                if route.view_factory:
                    view = route.view_factory()
                elif route.route_id in self._view_factories:
                    view = self._view_factories[route.route_id]()
                else:
                    # Create default placeholder view
                    view = self._create_placeholder_view(route)

                # Cache the view
                self._view_cache[route.route_id] = view

                # Notify view load callbacks
                self._notify_view_load_callbacks(route, view)

                logger.debug(f"View loaded successfully: {route.route_id}")
                return view

            finally:
                self._loading_views.pop(route.route_id, None)

        except Exception as e:
            logger.error(f"Error loading view for {route.route_id}: {e}")
            self._loading_views.pop(route.route_id, None)
            return None

    def _create_placeholder_view(self, route: NavigationRoute) -> ft.Control:
        """Create a placeholder view for a route."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        name=route.icon,
                        size=self.get_breakpoint_value(64, 80, 96, 128),
                        color=palette.primary
                    ),
                    ft.Text(
                        route.title,
                        style=self.get_text_style("headlineMedium"),
                        color=palette.on_surface,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        f"Route: {route.path}",
                        style=self.get_text_style("bodyMedium"),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        "View implementation pending",
                        style=self.get_text_style("bodySmall"),
                        color=palette.outline,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.lg
            ),
            alignment=ft.alignment.center,
            expand=True
        )

    def _update_content_view(self, view: ft.Control):
        """Update the content container with new view."""
        try:
            if self._content_container:
                self._content_container.content = view
                self._content_container.update()
        except Exception as e:
            logger.error(f"Error updating content view: {e}")

    def _show_loading(self, show: bool):
        """Show or hide loading overlay."""
        try:
            if self._loading_overlay:
                self._loading_overlay.visible = show
                self._loading_overlay.update()
        except Exception as e:
            logger.error(f"Error updating loading overlay: {e}")

    def _add_to_history(self, route: NavigationRoute, state_data: Dict[str, Any]):
        """Add current route to navigation history."""
        try:
            # Remove any entries after current index (for new navigation)
            if self._history_index < len(self._history) - 1:
                self._history = self._history[:self._history_index + 1]

            # Add new entry
            entry = NavigationHistoryEntry(
                route_id=route.route_id,
                path=route.path,
                title=route.title,
                timestamp=datetime.now(timezone.utc),
                state_data=state_data
            )

            self._history.append(entry)
            self._history_index = len(self._history) - 1

            # Limit history size
            if len(self._history) > self._max_history_size:
                self._history = self._history[-self._max_history_size:]
                self._history_index = len(self._history) - 1

        except Exception as e:
            logger.error(f"Error adding to history: {e}")

    def _update_breadcrumbs(self):
        """Update breadcrumb navigation."""
        try:
            if not self._current_route:
                self._breadcrumbs = []
                return

            breadcrumbs = []
            route = self._current_route

            # Build breadcrumb chain
            while route:
                breadcrumbs.insert(0, BreadcrumbItem(
                    route_id=route.route_id,
                    title=route.title,
                    path=route.path
                ))

                # Get parent route if exists
                if route.parent_route and route.parent_route in self._routes:
                    route = self._routes[route.parent_route]
                else:
                    break

            self._breadcrumbs = breadcrumbs

        except Exception as e:
            logger.error(f"Error updating breadcrumbs: {e}")

    # Callback Management
    def add_route_change_callback(self, callback: Callable):
        """Add route change callback."""
        if callback not in self._route_change_callbacks:
            self._route_change_callbacks.append(callback)

    def remove_route_change_callback(self, callback: Callable):
        """Remove route change callback."""
        if callback in self._route_change_callbacks:
            self._route_change_callbacks.remove(callback)

    def add_view_load_callback(self, callback: Callable):
        """Add view load callback."""
        if callback not in self._view_load_callbacks:
            self._view_load_callbacks.append(callback)

    def remove_view_load_callback(self, callback: Callable):
        """Remove view load callback."""
        if callback in self._view_load_callbacks:
            self._view_load_callbacks.remove(callback)

    def _notify_route_change_callbacks(self, route: NavigationRoute, state_data: Optional[Dict[str, Any]]):
        """Notify route change callbacks."""
        for callback in self._route_change_callbacks:
            try:
                callback(route, state_data)
            except Exception as e:
                logger.error(f"Error in route change callback: {e}")

    def _notify_view_load_callbacks(self, route: NavigationRoute, view: ft.Control):
        """Notify view load callbacks."""
        for callback in self._view_load_callbacks:
            try:
                callback(route, view)
            except Exception as e:
                logger.error(f"Error in view load callback: {e}")

    # Public Properties and Methods
    @property
    def current_route(self) -> Optional[NavigationRoute]:
        """Get current navigation route."""
        return self._current_route

    @property
    def current_view(self) -> Optional[ft.Control]:
        """Get current view."""
        return self._current_view

    @property
    def navigation_state(self) -> NavigationState:
        """Get current navigation state."""
        return self._navigation_state

    @property
    def breadcrumbs(self) -> List[BreadcrumbItem]:
        """Get current breadcrumbs."""
        return self._breadcrumbs.copy()

    @property
    def history(self) -> List[NavigationHistoryEntry]:
        """Get navigation history."""
        return self._history.copy()

    def get_route(self, route_id: str) -> Optional[NavigationRoute]:
        """Get route by ID."""
        return self._routes.get(route_id)

    def get_all_routes(self) -> Dict[str, NavigationRoute]:
        """Get all registered routes."""
        return self._routes.copy()

    def clear_cache(self, route_id: Optional[str] = None):
        """
        Clear view cache.

        Args:
            route_id: Specific route to clear, or None to clear all
        """
        try:
            if route_id:
                self._view_cache.pop(route_id, None)
                logger.debug(f"Cache cleared for route: {route_id}")
            else:
                self._view_cache.clear()
                logger.debug("All view cache cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")

    def clear_history(self):
        """Clear navigation history."""
        try:
            self._history.clear()
            self._history_index = -1
            logger.debug("Navigation history cleared")
        except Exception as e:
            logger.error(f"Error clearing history: {e}")

    # Error Handling and Validation
    def validate_route(self, route: NavigationRoute) -> Tuple[bool, str]:
        """
        Validate a navigation route.

        Args:
            route: Route to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check required fields
            if not route.route_id:
                return False, "Route ID is required"

            if not route.path:
                return False, "Route path is required"

            if not route.title:
                return False, "Route title is required"

            # Check for duplicate route ID
            if route.route_id in self._routes:
                existing_route = self._routes[route.route_id]
                if existing_route != route:
                    return False, f"Route ID '{route.route_id}' already exists"

            # Validate path format
            if not route.path.startswith('/'):
                return False, "Route path must start with '/'"

            # Validate parent route exists if specified
            if route.parent_route and route.parent_route not in self._routes:
                return False, f"Parent route '{route.parent_route}' does not exist"

            # Check for circular dependencies
            if self._has_circular_dependency(route):
                return False, "Circular dependency detected in route hierarchy"

            return True, ""

        except Exception as e:
            logger.error(f"Error validating route: {e}")
            return False, f"Validation error: {str(e)}"

    def _has_circular_dependency(self, route: NavigationRoute) -> bool:
        """Check for circular dependencies in route hierarchy."""
        try:
            visited = set()
            current = route

            while current and current.parent_route:
                if current.route_id in visited:
                    return True
                visited.add(current.route_id)

                if current.parent_route in self._routes:
                    current = self._routes[current.parent_route]
                else:
                    break

            return False

        except Exception:
            return True  # Assume circular dependency on error

    def validate_navigation_request(self, route_id: str) -> Tuple[bool, str]:
        """
        Validate a navigation request.

        Args:
            route_id: Route ID to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check if route exists
            if route_id not in self._routes:
                return False, f"Route '{route_id}' not found"

            route = self._routes[route_id]

            # Check if route requires authentication (placeholder for future implementation)
            if route.requires_auth:
                # TODO: Implement authentication check
                pass

            # Check if navigation is currently in progress
            if self._navigation_state == NavigationState.NAVIGATING:
                return False, "Navigation already in progress"

            # Check if view is currently loading
            if route_id in self._loading_views:
                return False, f"View for route '{route_id}' is already loading"

            return True, ""

        except Exception as e:
            logger.error(f"Error validating navigation request: {e}")
            return False, f"Validation error: {str(e)}"

    def handle_navigation_error(self, route_id: str, error: Exception):
        """
        Handle navigation errors with recovery strategies.

        Args:
            route_id: Route ID that failed
            error: Exception that occurred
        """
        try:
            logger.error(f"Navigation error for route '{route_id}': {error}")

            # Update navigation state
            self._navigation_state = NavigationState.ERROR
            self._show_loading(False)

            # Clear loading state
            self._loading_views.pop(route_id, None)

            # Show error view
            error_view = self._create_error_view(route_id, error)
            self._update_content_view(error_view)

            # Notify error callbacks
            self._notify_error_callbacks(route_id, error)

            # Attempt recovery strategies
            self._attempt_error_recovery(route_id, error)

        except Exception as e:
            logger.error(f"Error handling navigation error: {e}")

    def _create_error_view(self, route_id: str, error: Exception) -> ft.Control:
        """Create an error view for failed navigation."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        name=ft.Icons.ERROR_OUTLINE,
                        size=self.get_breakpoint_value(64, 80, 96, 128),
                        color=palette.error
                    ),
                    ft.Text(
                        "Navigation Error",
                        style=self.get_text_style("headlineMedium"),
                        color=palette.error,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        f"Failed to load: {route_id}",
                        style=self.get_text_style("bodyLarge"),
                        color=palette.on_surface,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        str(error),
                        style=self.get_text_style("bodySmall"),
                        color=palette.on_surface_variant,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Row(
                        controls=[
                            ft.ElevatedButton(
                                text="Retry",
                                icon=ft.Icons.REFRESH,
                                on_click=lambda _: asyncio.create_task(self.navigate_to(route_id, force_reload=True))
                            ),
                            ft.TextButton(
                                text="Go Back",
                                icon=ft.Icons.ARROW_BACK,
                                on_click=lambda _: asyncio.create_task(self.navigate_back())
                            )
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=spacing.md
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.lg
            ),
            alignment=ft.alignment.center,
            expand=True
        )

    def _attempt_error_recovery(self, route_id: str, error: Exception):
        """Attempt to recover from navigation errors."""
        try:
            # Clear cache for the failed route
            self.clear_cache(route_id)

            # If this was the initial route, try to navigate to dashboard
            if route_id == self._initial_route and route_id != "dashboard":
                asyncio.create_task(self.navigate_to("dashboard"))

        except Exception as e:
            logger.error(f"Error during recovery attempt: {e}")

    def _notify_error_callbacks(self, route_id: str, error: Exception):
        """Notify error callbacks."""
        for callback in self._error_callbacks:
            try:
                callback(route_id, error)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")

    def add_error_callback(self, callback: Callable):
        """Add error callback."""
        if callback not in self._error_callbacks:
            self._error_callbacks.append(callback)

    def remove_error_callback(self, callback: Callable):
        """Remove error callback."""
        if callback in self._error_callbacks:
            self._error_callbacks.remove(callback)

    # Utility Methods
    def get_navigation_stats(self) -> Dict[str, Any]:
        """Get navigation statistics."""
        return {
            "total_routes": len(self._routes),
            "cached_views": len(self._view_cache),
            "history_size": len(self._history),
            "current_route": self._current_route.route_id if self._current_route else None,
            "navigation_state": self._navigation_state.value,
            "can_go_back": self.can_navigate_back(),
            "can_go_forward": self.can_navigate_forward()
        }

    def cleanup(self):
        """Clean up resources and callbacks."""
        try:
            self._route_change_callbacks.clear()
            self._view_load_callbacks.clear()
            self._error_callbacks.clear()
            self._view_cache.clear()
            self._view_factories.clear()
            self._loading_views.clear()
            self._on_navigation_change = None
            logger.debug("NavigationControllerUI cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
