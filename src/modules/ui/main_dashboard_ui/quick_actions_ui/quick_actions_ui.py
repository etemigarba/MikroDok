"""
Module: quick_actions_ui
Description: Quick start action buttons UI component for MikroDok application.
            Provides customizable quick action buttons for creating models, importing documents,
            starting training, and other common operations. Features responsive design,
            theme integration, accessibility support, and comprehensive action management.
Phase: 1
Location: /src/modules/ui/main_dashboard_ui/quick_actions_ui/
"""

# Standard library imports
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import ThemeAwareUserControl


# Configure logging
logger = logging.getLogger(__name__)


class ActionLayout(Enum):
    """Layout options for quick actions."""
    GRID = "grid"
    LIST = "list"
    COMPACT = "compact"
    CAROUSEL = "carousel"


class ActionSize(Enum):
    """Size variants for action buttons."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    EXTRA_LARGE = "extra_large"


class ActionStyle(Enum):
    """Style variants for action buttons."""
    CARD = "card"
    BUTTON = "button"
    TILE = "tile"
    MINIMAL = "minimal"


@dataclass
class QuickAction:
    """Quick action button configuration."""
    title: str
    description: str
    icon: str
    action: Callable
    enabled: bool = True
    badge_text: Optional[str] = None
    badge_color: Optional[str] = None
    category: Optional[str] = None
    priority: int = 0
    tooltip: Optional[str] = None
    keyboard_shortcut: Optional[str] = None
    confirmation_required: bool = False
    confirmation_message: Optional[str] = None


@dataclass
class QuickActionsConfig:
    """Configuration for quick actions UI component."""
    layout: ActionLayout = ActionLayout.GRID
    action_size: ActionSize = ActionSize.MEDIUM
    action_style: ActionStyle = ActionStyle.CARD
    columns_mobile: int = 2
    columns_tablet: int = 3
    columns_desktop: int = 3
    columns_large: int = 4
    show_titles: bool = True
    show_descriptions: bool = True
    show_badges: bool = True
    enable_animations: bool = True
    enable_hover_effects: bool = True
    enable_keyboard_shortcuts: bool = True
    auto_arrange_by_priority: bool = True
    max_actions_per_row: int = 6
    spacing_between_actions: float = 12.0
    action_min_height: float = 120.0
    action_max_height: float = 200.0
    enable_tooltips: bool = True
    enable_confirmation_dialogs: bool = True


class QuickActionsUI(ThemeAwareUserControl):
    """
    Quick actions UI component for MikroDok application.
    
    Provides customizable quick action buttons with:
    - Responsive grid/list layouts
    - Theme-aware styling and animations
    - Configurable action buttons with icons and descriptions
    - Badge support for notifications and status
    - Keyboard shortcut support
    - Accessibility features and tooltips
    - Action confirmation dialogs
    - Priority-based action arrangement
    - Multiple layout and style options
    - Performance optimization
    """

    def __init__(
        self,
        actions: Optional[List[QuickAction]] = None,
        config: Optional[QuickActionsConfig] = None,
        on_action_triggered: Optional[Callable[[str, QuickAction], None]] = None,
        **kwargs
    ):
        """
        Initialize quick actions UI component.
        
        Args:
            actions: List of quick actions to display
            config: Configuration for the component
            on_action_triggered: Callback for action events
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._config = config or QuickActionsConfig()
        self._actions = actions or []
        self._on_action_triggered = on_action_triggered
        
        # Component state
        self._action_buttons: Dict[str, ft.Control] = {}
        self._confirmation_dialog: Optional[ft.AlertDialog] = None
        self._pending_action: Optional[QuickAction] = None
        self._is_refreshing = False
        
        # UI components
        self._main_container = None
        self._actions_grid = None
        self._empty_state = None
        
        # Initialize component
        self._sort_actions_by_priority()
        
        logger.info(f"QuickActionsUI initialized with {len(self._actions)} actions")

    def build(self) -> ft.Control:
        """Build the quick actions UI component."""
        try:
            self._ensure_theme_manager()
            self._ensure_responsive_manager()
            
            return self._create_main_container()
            
        except Exception as e:
            logger.error(f"Error building QuickActionsUI: {e}")
            return self._create_error_state(str(e))

    def _create_main_container(self) -> ft.Control:
        """Create the main container for quick actions."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        
        if not self._actions:
            return self._create_empty_state()
        
        # Create actions layout based on configuration
        if self._config.layout == ActionLayout.GRID:
            content = self._create_grid_layout()
        elif self._config.layout == ActionLayout.LIST:
            content = self._create_list_layout()
        elif self._config.layout == ActionLayout.COMPACT:
            content = self._create_compact_layout()
        elif self._config.layout == ActionLayout.CAROUSEL:
            content = self._create_carousel_layout()
        else:
            content = self._create_grid_layout()  # Default fallback
        
        self._main_container = ft.Container(
            content=content,
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(self.get_breakpoint_value(8, 12, 16, 20)),
            border=ft.border.all(1, palette.outline),
            padding=ft.padding.all(spacing.md),
            animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT) if self._config.enable_animations else None
        )
        
        return self._main_container

    def _sort_actions_by_priority(self) -> None:
        """Sort actions by priority if enabled."""
        if self._config.auto_arrange_by_priority:
            self._actions.sort(key=lambda action: (-action.priority, action.title))

    def _create_grid_layout(self) -> ft.Control:
        """Create grid layout for actions."""
        action_buttons = [self._create_action_button(action) for action in self._actions]
        
        return self.create_responsive_grid(
            children=action_buttons,
            mobile_cols=self._config.columns_mobile,
            tablet_cols=self._config.columns_tablet,
            desktop_cols=self._config.columns_desktop,
            large_cols=self._config.columns_large,
            spacing=self.get_spacing().sm
        )

    def _create_list_layout(self) -> ft.Control:
        """Create list layout for actions."""
        action_buttons = [self._create_action_button(action, is_list_item=True) for action in self._actions]
        
        return ft.Column(
            controls=action_buttons,
            spacing=self.get_spacing().xs,
            scroll=ft.ScrollMode.AUTO
        )

    def _create_compact_layout(self) -> ft.Control:
        """Create compact layout for actions."""
        action_buttons = [self._create_compact_action_button(action) for action in self._actions]
        
        return ft.Wrap(
            controls=action_buttons,
            spacing=self.get_spacing().xs,
            run_spacing=self.get_spacing().xs
        )

    def _create_carousel_layout(self) -> ft.Control:
        """Create carousel layout for actions."""
        action_buttons = [self._create_action_button(action) for action in self._actions]
        
        return ft.Row(
            controls=action_buttons,
            spacing=self.get_spacing().sm,
            scroll=ft.ScrollMode.AUTO
        )

    def _create_action_button(self, action: QuickAction, is_list_item: bool = False) -> ft.Control:
        """Create individual action button."""
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        icons = self.get_icons()

        # Get size configuration
        icon_size, button_height, text_style = self._get_size_config()

        # Create button content based on style
        if self._config.action_style == ActionStyle.CARD:
            return self._create_card_style_button(action, icon_size, button_height, is_list_item)
        elif self._config.action_style == ActionStyle.BUTTON:
            return self._create_button_style_button(action, icon_size, button_height)
        elif self._config.action_style == ActionStyle.TILE:
            return self._create_tile_style_button(action, icon_size, button_height, is_list_item)
        elif self._config.action_style == ActionStyle.MINIMAL:
            return self._create_minimal_style_button(action, icon_size, button_height)
        else:
            return self._create_card_style_button(action, icon_size, button_height, is_list_item)

    def _create_card_style_button(self, action: QuickAction, icon_size: float, button_height: float, is_list_item: bool = False) -> ft.Control:
        """Create card-style action button."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        # Create icon with badge if needed
        icon_control = self._create_icon_with_badge(action, icon_size)

        # Create text content
        text_controls = []
        if self._config.show_titles:
            text_controls.append(
                ft.Text(
                    action.title,
                    style=self.get_text_style("bodyMedium"),
                    color=palette.text_primary if action.enabled else palette.text_secondary,
                    weight=ft.FontWeight.W_500,
                    text_align=ft.TextAlign.CENTER if not is_list_item else ft.TextAlign.LEFT,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS
                )
            )

        if self._config.show_descriptions and action.description:
            text_controls.append(
                ft.Text(
                    action.description,
                    style=self.get_text_style("bodySmall"),
                    color=palette.text_secondary,
                    text_align=ft.TextAlign.CENTER if not is_list_item else ft.TextAlign.LEFT,
                    max_lines=3,
                    overflow=ft.TextOverflow.ELLIPSIS
                )
            )

        # Layout content
        if is_list_item:
            content = ft.Row(
                controls=[
                    icon_control,
                    ft.Container(width=spacing.md),
                    ft.Column(
                        controls=text_controls,
                        spacing=spacing.xs,
                        expand=True
                    )
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )
        else:
            content = ft.Column(
                controls=[icon_control] + text_controls,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.xs
            )

        return ft.Container(
            content=content,
            bgcolor=palette.surface_variant if action.enabled else palette.surface,
            border_radius=ft.border_radius.all(self.get_breakpoint_value(8, 10, 12, 14)),
            border=ft.border.all(1, palette.outline),
            padding=ft.padding.all(spacing.md),
            height=button_height if not is_list_item else None,
            on_click=lambda _: self._handle_action_click(action) if action.enabled else None,
            ink=True,
            animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT) if self._config.enable_animations else None,
            tooltip=action.tooltip or action.description if self._config.enable_tooltips else None
        )

    def _create_button_style_button(self, action: QuickAction, icon_size: float, button_height: float) -> ft.Control:
        """Create button-style action button."""
        palette = self.get_palette()

        return ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        name=self.get_icon(action.icon),
                        size=icon_size,
                        color=palette.on_primary if action.enabled else palette.text_secondary
                    ),
                    ft.Text(
                        action.title,
                        style=self.get_text_style("bodyMedium"),
                        color=palette.on_primary if action.enabled else palette.text_secondary,
                        weight=ft.FontWeight.W_500
                    )
                ],
                spacing=self.get_spacing().xs,
                alignment=ft.MainAxisAlignment.CENTER
            ),
            bgcolor=palette.primary if action.enabled else palette.surface,
            color=palette.on_primary if action.enabled else palette.text_secondary,
            height=button_height,
            on_click=lambda _: self._handle_action_click(action) if action.enabled else None,
            tooltip=action.tooltip or action.description if self._config.enable_tooltips else None
        )

    def _create_tile_style_button(self, action: QuickAction, icon_size: float, button_height: float, is_list_item: bool = False) -> ft.Control:
        """Create tile-style action button."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        icon_control = self._create_icon_with_badge(action, icon_size)

        content = ft.ListTile(
            leading=icon_control,
            title=ft.Text(
                action.title,
                style=self.get_text_style("bodyMedium"),
                color=palette.text_primary if action.enabled else palette.text_secondary,
                weight=ft.FontWeight.W_500
            ),
            subtitle=ft.Text(
                action.description,
                style=self.get_text_style("bodySmall"),
                color=palette.text_secondary
            ) if self._config.show_descriptions and action.description else None,
            on_click=lambda _: self._handle_action_click(action) if action.enabled else None,
            bgcolor=palette.surface_variant if action.enabled else palette.surface,
            shape=ft.RoundedRectangleBorder(radius=self.get_breakpoint_value(8, 10, 12, 14))
        )

        return content

    def _create_minimal_style_button(self, action: QuickAction, icon_size: float, button_height: float) -> ft.Control:
        """Create minimal-style action button."""
        palette = self.get_palette()

        return ft.IconButton(
            icon=self.get_icon(action.icon),
            icon_size=icon_size,
            icon_color=palette.primary if action.enabled else palette.text_secondary,
            bgcolor=palette.surface_variant if action.enabled else None,
            on_click=lambda _: self._handle_action_click(action) if action.enabled else None,
            tooltip=f"{action.title}\n{action.description}" if self._config.enable_tooltips else None
        )

    def _create_compact_action_button(self, action: QuickAction) -> ft.Control:
        """Create compact action button for compact layout."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        icon_size = self.get_breakpoint_value(16, 18, 20, 22)

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        name=self.get_icon(action.icon),
                        size=icon_size,
                        color=palette.primary if action.enabled else palette.text_secondary
                    ),
                    ft.Text(
                        action.title,
                        style=self.get_text_style("bodySmall"),
                        color=palette.text_primary if action.enabled else palette.text_secondary,
                        weight=ft.FontWeight.W_500
                    )
                ],
                spacing=spacing.xs,
                alignment=ft.MainAxisAlignment.START
            ),
            bgcolor=palette.surface_variant if action.enabled else palette.surface,
            border_radius=ft.border_radius.all(self.get_breakpoint_value(6, 8, 10, 12)),
            border=ft.border.all(1, palette.outline),
            padding=ft.padding.symmetric(horizontal=spacing.sm, vertical=spacing.xs),
            on_click=lambda _: self._handle_action_click(action) if action.enabled else None,
            ink=True,
            tooltip=action.tooltip or action.description if self._config.enable_tooltips else None
        )

    def _create_icon_with_badge(self, action: QuickAction, icon_size: float) -> ft.Control:
        """Create icon with optional badge."""
        palette = self.get_palette()

        icon = ft.Icon(
            name=self.get_icon(action.icon),
            size=icon_size,
            color=palette.primary if action.enabled else palette.text_secondary
        )

        if not self._config.show_badges or not action.badge_text:
            return icon

        # Create badge
        badge_color = action.badge_color or palette.error
        badge = ft.Container(
            content=ft.Text(
                action.badge_text,
                style=self.get_text_style("labelSmall"),
                color=palette.on_error,
                weight=ft.FontWeight.W_600
            ),
            bgcolor=badge_color,
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.symmetric(horizontal=6, vertical=2),
            alignment=ft.alignment.center
        )

        return ft.Stack(
            controls=[
                icon,
                ft.Positioned(
                    right=-4,
                    top=-4,
                    child=badge
                )
            ]
        )

    def _get_size_config(self) -> tuple[float, float, str]:
        """Get size configuration based on action size setting."""
        if self._config.action_size == ActionSize.SMALL:
            return (
                self.get_breakpoint_value(16, 18, 20, 22),  # icon_size
                self.get_breakpoint_value(80, 90, 100, 110),  # button_height
                "bodySmall"  # text_style
            )
        elif self._config.action_size == ActionSize.MEDIUM:
            return (
                self.get_breakpoint_value(24, 28, 32, 36),  # icon_size
                self.get_breakpoint_value(120, 130, 140, 150),  # button_height
                "bodyMedium"  # text_style
            )
        elif self._config.action_size == ActionSize.LARGE:
            return (
                self.get_breakpoint_value(32, 36, 40, 44),  # icon_size
                self.get_breakpoint_value(160, 170, 180, 190),  # button_height
                "bodyLarge"  # text_style
            )
        elif self._config.action_size == ActionSize.EXTRA_LARGE:
            return (
                self.get_breakpoint_value(40, 44, 48, 52),  # icon_size
                self.get_breakpoint_value(200, 210, 220, 230),  # button_height
                "titleSmall"  # text_style
            )
        else:
            # Default to medium
            return (
                self.get_breakpoint_value(24, 28, 32, 36),
                self.get_breakpoint_value(120, 130, 140, 150),
                "bodyMedium"
            )

    def _handle_action_click(self, action: QuickAction) -> None:
        """Handle action button click."""
        try:
            if not action.enabled:
                return

            # Check if confirmation is required
            if action.confirmation_required and self._config.enable_confirmation_dialogs:
                self._show_confirmation_dialog(action)
                return

            # Execute action
            self._execute_action(action)

        except Exception as e:
            logger.error(f"Error handling action click for '{action.title}': {e}")
            self._show_error_dialog(f"Failed to execute action: {str(e)}")

    def _execute_action(self, action: QuickAction) -> None:
        """Execute the action."""
        try:
            # Call the action callback
            if action.action:
                action.action()

            # Notify parent component
            if self._on_action_triggered:
                self._on_action_triggered(action.title.lower().replace(' ', '_'), action)

            logger.info(f"Action executed: {action.title}")

        except Exception as e:
            logger.error(f"Error executing action '{action.title}': {e}")
            raise

    def _show_confirmation_dialog(self, action: QuickAction) -> None:
        """Show confirmation dialog for action."""
        if not self.page:
            return

        palette = self.get_palette()

        self._pending_action = action

        self._confirmation_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                f"Confirm {action.title}",
                style=self.get_text_style("titleMedium"),
                color=palette.text_primary
            ),
            content=ft.Text(
                action.confirmation_message or f"Are you sure you want to {action.title.lower()}?",
                style=self.get_text_style("bodyMedium"),
                color=palette.text_secondary
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=self._cancel_confirmation
                ),
                ft.ElevatedButton(
                    "Confirm",
                    on_click=self._confirm_action
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )

        self.page.dialog = self._confirmation_dialog
        self._confirmation_dialog.open = True
        self.page.update()

    def _cancel_confirmation(self, e) -> None:
        """Cancel action confirmation."""
        if self._confirmation_dialog:
            self._confirmation_dialog.open = False
            self.page.update()
        self._pending_action = None

    def _confirm_action(self, e) -> None:
        """Confirm and execute pending action."""
        if self._confirmation_dialog:
            self._confirmation_dialog.open = False
            self.page.update()

        if self._pending_action:
            self._execute_action(self._pending_action)
            self._pending_action = None

    def _show_error_dialog(self, message: str) -> None:
        """Show error dialog."""
        if not self.page:
            return

        palette = self.get_palette()

        error_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                "Error",
                style=self.get_text_style("titleMedium"),
                color=palette.error
            ),
            content=ft.Text(
                message,
                style=self.get_text_style("bodyMedium"),
                color=palette.text_secondary
            ),
            actions=[
                ft.TextButton(
                    "OK",
                    on_click=lambda _: self._close_error_dialog()
                )
            ]
        )

        self.page.dialog = error_dialog
        error_dialog.open = True
        self.page.update()

    def _close_error_dialog(self) -> None:
        """Close error dialog."""
        if self.page and self.page.dialog:
            self.page.dialog.open = False
            self.page.update()

    def _create_empty_state(self) -> ft.Control:
        """Create empty state when no actions are available."""
        palette = self.get_palette()
        spacing = self.get_spacing()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        name=ft.Icons.TOUCH_APP,
                        size=self.get_breakpoint_value(48, 56, 64, 72),
                        color=palette.text_secondary
                    ),
                    ft.Text(
                        "No Quick Actions",
                        style=self.get_text_style("titleMedium"),
                        color=palette.text_primary,
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Text(
                        "Add quick actions to get started with common tasks",
                        style=self.get_text_style("bodyMedium"),
                        color=palette.text_secondary,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.md
            ),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(self.get_breakpoint_value(8, 12, 16, 20)),
            border=ft.border.all(1, palette.outline),
            padding=ft.padding.all(spacing.xl),
            alignment=ft.alignment.center,
            height=self.get_breakpoint_value(200, 220, 240, 260)
        )

    def _create_error_state(self, error_message: str) -> ft.Control:
        """Create error state display."""
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
                        "Error Loading Actions",
                        style=self.get_text_style("titleMedium"),
                        color=palette.error,
                        weight=ft.FontWeight.W_500
                    ),
                    ft.Text(
                        error_message,
                        style=self.get_text_style("bodyMedium"),
                        color=palette.text_secondary,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=spacing.md
            ),
            bgcolor=palette.surface,
            border_radius=ft.border_radius.all(self.get_breakpoint_value(8, 12, 16, 20)),
            border=ft.border.all(1, palette.error),
            padding=ft.padding.all(spacing.xl),
            alignment=ft.alignment.center,
            height=self.get_breakpoint_value(200, 220, 240, 260)
        )

    # Public API methods

    def set_actions(self, actions: List[QuickAction]) -> None:
        """
        Set the list of quick actions.

        Args:
            actions: List of quick actions to display
        """
        try:
            self._actions = actions or []
            self._sort_actions_by_priority()
            self._action_buttons.clear()

            if self.page:
                self.content = self._create_main_container()
                self.page.update()

            logger.debug(f"Actions updated: {len(self._actions)} actions")

        except Exception as e:
            logger.error(f"Error setting actions: {e}")

    def add_action(self, action: QuickAction) -> None:
        """
        Add a new quick action.

        Args:
            action: Quick action to add
        """
        try:
            self._actions.append(action)
            self._sort_actions_by_priority()

            if self.page:
                self.content = self._create_main_container()
                self.page.update()

            logger.debug(f"Action added: {action.title}")

        except Exception as e:
            logger.error(f"Error adding action: {e}")

    def remove_action(self, title: str) -> bool:
        """
        Remove an action by title.

        Args:
            title: Title of the action to remove

        Returns:
            True if action was removed, False if not found
        """
        try:
            original_count = len(self._actions)
            self._actions = [action for action in self._actions if action.title != title]

            if len(self._actions) < original_count:
                if self.page:
                    self.content = self._create_main_container()
                    self.page.update()

                logger.debug(f"Action removed: {title}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error removing action: {e}")
            return False

    def update_action(self, title: str, **kwargs) -> bool:
        """
        Update an existing action.

        Args:
            title: Title of the action to update
            **kwargs: Properties to update

        Returns:
            True if action was updated, False if not found
        """
        try:
            for action in self._actions:
                if action.title == title:
                    # Update action properties
                    for key, value in kwargs.items():
                        if hasattr(action, key):
                            setattr(action, key, value)

                    self._sort_actions_by_priority()

                    if self.page:
                        self.content = self._create_main_container()
                        self.page.update()

                    logger.debug(f"Action updated: {title}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error updating action: {e}")
            return False

    def set_config(self, config: QuickActionsConfig) -> None:
        """
        Update the component configuration.

        Args:
            config: New configuration
        """
        try:
            self._config = config
            self._sort_actions_by_priority()

            if self.page:
                self.content = self._create_main_container()
                self.page.update()

            logger.debug("Configuration updated")

        except Exception as e:
            logger.error(f"Error setting config: {e}")

    def get_actions(self) -> List[QuickAction]:
        """
        Get the current list of actions.

        Returns:
            List of current quick actions
        """
        return self._actions.copy()

    def get_config(self) -> QuickActionsConfig:
        """
        Get the current configuration.

        Returns:
            Current configuration
        """
        return self._config

    def enable_action(self, title: str) -> bool:
        """
        Enable an action by title.

        Args:
            title: Title of the action to enable

        Returns:
            True if action was found and enabled
        """
        return self.update_action(title, enabled=True)

    def disable_action(self, title: str) -> bool:
        """
        Disable an action by title.

        Args:
            title: Title of the action to disable

        Returns:
            True if action was found and disabled
        """
        return self.update_action(title, enabled=False)

    def set_action_badge(self, title: str, badge_text: Optional[str], badge_color: Optional[str] = None) -> bool:
        """
        Set badge for an action.

        Args:
            title: Title of the action
            badge_text: Badge text (None to remove badge)
            badge_color: Badge color (optional)

        Returns:
            True if action was found and updated
        """
        return self.update_action(title, badge_text=badge_text, badge_color=badge_color)

    def refresh(self) -> None:
        """Refresh the component display."""
        try:
            if self._is_refreshing:
                return

            self._is_refreshing = True

            if self.page:
                self.content = self._create_main_container()
                self.page.update()

            logger.debug("Component refreshed")

        except Exception as e:
            logger.error(f"Error refreshing component: {e}")
        finally:
            self._is_refreshing = False

    def _on_theme_change(self) -> None:
        """Handle theme change events."""
        try:
            if self.page:
                self.refresh()
        except Exception as e:
            logger.error(f"Error handling theme change: {e}")

    def _on_responsive_change(self, screen_size: tuple) -> None:
        """Handle responsive layout changes."""
        try:
            if self._last_screen_size != screen_size:
                self._last_screen_size = screen_size
                if self.page:
                    self.refresh()
        except Exception as e:
            logger.error(f"Error handling responsive change: {e}")


# Default quick actions for common MikroDok operations
def create_default_actions() -> List[QuickAction]:
    """Create default quick actions for MikroDok application."""
    return [
        QuickAction(
            title="Create Model",
            description="Start building a new language model",
            icon="ADD_CIRCLE",
            action=lambda: None,  # Placeholder - should be connected to actual functionality
            priority=10
        ),
        QuickAction(
            title="Import Documents",
            description="Add documents to your knowledge base",
            icon="UPLOAD_FILE",
            action=lambda: None,  # Placeholder
            priority=9
        ),
        QuickAction(
            title="Start Training",
            description="Begin model training process",
            icon="PLAY_ARROW",
            action=lambda: None,  # Placeholder
            priority=8
        ),
        QuickAction(
            title="System Monitor",
            description="View detailed system performance",
            icon="MONITOR",
            action=lambda: None,  # Placeholder
            priority=7
        ),
        QuickAction(
            title="Search Documents",
            description="Find content in your knowledge base",
            icon="SEARCH",
            action=lambda: None,  # Placeholder
            priority=6
        ),
        QuickAction(
            title="Chat Interface",
            description="Interact with your trained models",
            icon="CHAT",
            action=lambda: None,  # Placeholder
            priority=5
        )
    ]
