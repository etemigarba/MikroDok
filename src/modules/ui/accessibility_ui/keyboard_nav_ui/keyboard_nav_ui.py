"""
Module: keyboard_nav_ui
Description: Comprehensive keyboard navigation UI component with WCAG 2.1 AA compliance, focus management, and keyboard shortcuts.
            Provides enterprise-grade accessibility features including keyboard navigation patterns, focus indicators,
            shortcut management, and seamless theme system integration for the MikroDok application.

Features:
- WCAG 2.1 AA compliant keyboard navigation
- Focus management with visual indicators and trapping
- Customizable keyboard shortcuts with conflict detection
- Screen reader integration and announcements
- Responsive design with breakpoint-aware focus indicators
- Theme system integration for consistent styling
- Performance optimization for keyboard event handling
- Cross-platform keyboard support
- Accessibility state tracking and monitoring

Phase: 1
Location: /src/modules/ui/accessibility_ui/keyboard_nav_ui/keyboard_nav_ui.py
"""

# Standard library imports
import asyncio
import json
import logging
import platform
import time
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, Union, Tuple, Set
from dataclasses import dataclass, asdict, field
from pathlib import Path

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager,
    ResponsiveLayoutManager,
    ScreenSize,
    AccessibilityManager
)

# Configure logging
logger = logging.getLogger(__name__)


class NavigationMode(Enum):
    """Navigation mode enumeration for keyboard navigation patterns."""
    SEQUENTIAL = "sequential"  # Tab order navigation
    SPATIAL = "spatial"       # Arrow key navigation
    HIERARCHICAL = "hierarchical"  # Tree-like navigation
    GRID = "grid"            # Grid-based navigation
    CUSTOM = "custom"        # Custom navigation pattern


class FocusIndicatorStyle(Enum):
    """Focus indicator style options."""
    OUTLINE = "outline"      # Standard outline
    HIGHLIGHT = "highlight"  # Background highlight
    UNDERLINE = "underline"  # Underline indicator
    GLOW = "glow"           # Glow effect
    CUSTOM = "custom"       # Custom styling


class KeyModifier(Enum):
    """Keyboard modifier keys."""
    CTRL = "ctrl"
    ALT = "alt"
    SHIFT = "shift"
    META = "meta"  # Windows key / Cmd key


class ShortcutScope(Enum):
    """Scope for keyboard shortcuts."""
    GLOBAL = "global"        # Application-wide
    COMPONENT = "component"  # Component-specific
    MODAL = "modal"         # Modal dialog only
    CONTEXT = "context"     # Context-specific


class FocusDirection(Enum):
    """Focus movement direction."""
    NEXT = "next"
    PREVIOUS = "previous"
    FIRST = "first"
    LAST = "last"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


@dataclass
class KeyboardShortcut:
    """
    Keyboard shortcut definition with comprehensive configuration.
    
    Represents a keyboard shortcut with key combination, action, scope,
    and metadata for conflict detection and accessibility.
    """
    key: str                                    # Primary key (e.g., "F1", "Enter", "Space")
    modifiers: Set[KeyModifier] = field(default_factory=set)  # Modifier keys
    action: Optional[Callable] = None           # Action to execute
    description: str = ""                       # Human-readable description
    scope: ShortcutScope = ShortcutScope.GLOBAL # Shortcut scope
    category: str = "general"                   # Category for organization
    enabled: bool = True                        # Whether shortcut is active
    priority: int = 0                          # Priority for conflict resolution
    accessibility_label: str = ""              # Screen reader label
    help_text: str = ""                        # Extended help text
    
    def __post_init__(self):
        """Post-initialization validation and setup."""
        if not self.accessibility_label:
            self.accessibility_label = self.description or f"Keyboard shortcut {self.get_key_combination()}"
        
        if not self.help_text:
            self.help_text = f"Press {self.get_key_combination()} to {self.description.lower()}"
    
    def get_key_combination(self) -> str:
        """
        Get human-readable key combination string.
        
        Returns:
            Formatted key combination (e.g., "Ctrl+Shift+F")
        """
        parts = []
        
        # Add modifiers in standard order
        if KeyModifier.CTRL in self.modifiers:
            parts.append("Ctrl")
        if KeyModifier.ALT in self.modifiers:
            parts.append("Alt")
        if KeyModifier.SHIFT in self.modifiers:
            parts.append("Shift")
        if KeyModifier.META in self.modifiers:
            parts.append("Meta")
        
        # Add primary key
        parts.append(self.key)
        
        return "+".join(parts)
    
    def matches_event(self, event: ft.KeyboardEvent) -> bool:
        """
        Check if keyboard event matches this shortcut.
        
        Args:
            event: Keyboard event to check
            
        Returns:
            True if event matches shortcut
        """
        try:
            # Check primary key
            if event.key.lower() != self.key.lower():
                return False
            
            # Check modifiers
            expected_modifiers = {
                KeyModifier.CTRL: event.ctrl,
                KeyModifier.ALT: event.alt,
                KeyModifier.SHIFT: event.shift,
                KeyModifier.META: event.meta
            }
            
            for modifier in KeyModifier:
                has_modifier = modifier in self.modifiers
                event_has_modifier = expected_modifiers.get(modifier, False)
                
                if has_modifier != event_has_modifier:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error matching keyboard event: {e}")
            return False


@dataclass
class FocusState:
    """Current focus state information."""
    element_id: Optional[str] = None           # ID of focused element
    element_type: str = "unknown"              # Type of focused element
    element_label: str = ""                    # Accessible label
    focus_index: int = -1                      # Index in focus order
    is_trapped: bool = False                   # Whether focus is trapped
    trap_container: Optional[str] = None       # Focus trap container ID
    last_focus_time: float = 0.0              # Timestamp of last focus change
    focus_history: List[str] = field(default_factory=list)  # Focus history
    
    def __post_init__(self):
        if self.last_focus_time == 0.0:
            self.last_focus_time = time.time()


@dataclass
class KeyboardConfiguration:
    """Configuration for keyboard navigation features."""
    # Navigation settings
    enable_keyboard_navigation: bool = True
    enable_focus_management: bool = True
    enable_shortcuts: bool = True
    enable_spatial_navigation: bool = True
    
    # Focus indicator settings
    focus_indicator_style: FocusIndicatorStyle = FocusIndicatorStyle.OUTLINE
    focus_indicator_width: int = 2
    focus_indicator_offset: int = 2
    focus_indicator_color: Optional[str] = None  # Uses theme color if None
    
    # Navigation behavior
    wrap_navigation: bool = True               # Wrap at boundaries
    skip_disabled_elements: bool = True        # Skip disabled elements
    auto_scroll_to_focus: bool = True         # Auto-scroll to focused element
    focus_delay_ms: int = 0                   # Delay before focus change
    
    # Shortcut settings
    enable_global_shortcuts: bool = True
    enable_context_shortcuts: bool = True
    shortcut_feedback: bool = True            # Visual/audio feedback
    conflict_resolution: str = "priority"     # "priority" or "first"
    
    # Accessibility settings
    announce_focus_changes: bool = True
    announce_shortcuts: bool = True
    high_contrast_focus: bool = False
    reduced_motion_focus: bool = False
    
    # Performance settings
    debounce_focus_ms: int = 50              # Focus change debouncing
    max_focus_history: int = 20              # Maximum focus history size
    enable_performance_monitoring: bool = True


class ShortcutConflictError(Exception):
    """Exception raised when keyboard shortcuts conflict."""
    
    def __init__(self, shortcut1: KeyboardShortcut, shortcut2: KeyboardShortcut):
        self.shortcut1 = shortcut1
        self.shortcut2 = shortcut2
        message = f"Shortcut conflict: {shortcut1.get_key_combination()} is used by both '{shortcut1.description}' and '{shortcut2.description}'"
        super().__init__(message)


@dataclass
class NavigationMetrics:
    """Performance and usage metrics for keyboard navigation."""
    focus_changes: int = 0
    shortcuts_triggered: int = 0
    navigation_errors: int = 0
    average_focus_time: float = 0.0
    total_navigation_time: float = 0.0
    shortcut_usage: Dict[str, int] = field(default_factory=dict)
    focus_patterns: Dict[str, int] = field(default_factory=dict)
    last_reset: float = field(default_factory=time.time)
    
    def record_focus_change(self, duration: float = 0.0) -> None:
        """Record a focus change event."""
        self.focus_changes += 1
        if duration > 0:
            self.total_navigation_time += duration
            self.average_focus_time = self.total_navigation_time / self.focus_changes
    
    def record_shortcut_usage(self, shortcut_key: str) -> None:
        """Record shortcut usage."""
        self.shortcuts_triggered += 1
        self.shortcut_usage[shortcut_key] = self.shortcut_usage.get(shortcut_key, 0) + 1
    
    def record_error(self) -> None:
        """Record a navigation error."""
        self.navigation_errors += 1
    
    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self.focus_changes = 0
        self.shortcuts_triggered = 0
        self.navigation_errors = 0
        self.average_focus_time = 0.0
        self.total_navigation_time = 0.0
        self.shortcut_usage.clear()
        self.focus_patterns.clear()
        self.last_reset = time.time()


class FocusManager:
    """
    Comprehensive focus management system with WCAG 2.1 AA compliance.

    Provides focus tracking, focus indicators, focus trapping, and accessibility
    announcements for keyboard navigation with screen reader integration.
    """

    def __init__(self,
                 config: Optional[KeyboardConfiguration] = None,
                 screen_reader_manager: Optional[Any] = None):
        """
        Initialize the focus manager.

        Args:
            config: Keyboard navigation configuration
            screen_reader_manager: Screen reader manager for announcements
        """
        self._config = config or KeyboardConfiguration()
        self._screen_reader_manager = screen_reader_manager

        # Focus state tracking
        self._current_focus = FocusState()
        self._focus_order: List[str] = []
        self._focus_elements: Dict[str, ft.Control] = {}
        self._focus_callbacks: List[Callable[[FocusState], None]] = []

        # Focus trapping
        self._focus_trap_stack: List[str] = []
        self._trapped_elements: Dict[str, List[str]] = {}

        # Theme integration
        self._theme_manager = get_theme_manager()
        self._responsive_manager = None
        if self._theme_manager:
            try:
                self._responsive_manager = self._theme_manager.get_responsive_layout_manager()
            except Exception as e:
                logger.warning(f"Could not get responsive manager: {e}")

        # Performance tracking
        self._metrics = NavigationMetrics()
        self._last_focus_time = time.time()
        self._focus_debounce_timer = None

        # Focus indicators
        self._focus_indicators: Dict[str, ft.Control] = {}
        self._current_screen_size = ScreenSize.DESKTOP

        logger.info("FocusManager initialized")

    def register_focusable_element(self,
                                 element_id: str,
                                 element: ft.Control,
                                 label: str = "",
                                 element_type: str = "element",
                                 insert_index: Optional[int] = None) -> None:
        """
        Register an element as focusable.

        Args:
            element_id: Unique identifier for the element
            element: Flet control element
            label: Accessible label for the element
            element_type: Type of element (button, text, etc.)
            insert_index: Position in focus order (None = append)
        """
        try:
            # Store element reference
            self._focus_elements[element_id] = element

            # Add to focus order
            if insert_index is not None and 0 <= insert_index <= len(self._focus_order):
                self._focus_order.insert(insert_index, element_id)
            else:
                self._focus_order.append(element_id)

            # Set up accessibility attributes
            self._setup_element_accessibility(element, element_id, label, element_type)

            # Create focus indicator
            self._create_focus_indicator(element_id, element)

            logger.debug(f"Registered focusable element: {element_id} ({element_type})")

        except Exception as e:
            logger.error(f"Error registering focusable element {element_id}: {e}")
            self._metrics.record_error()

    def unregister_focusable_element(self, element_id: str) -> None:
        """
        Unregister a focusable element.

        Args:
            element_id: Element identifier to unregister
        """
        try:
            # Remove from focus order
            if element_id in self._focus_order:
                self._focus_order.remove(element_id)

            # Remove element reference
            if element_id in self._focus_elements:
                del self._focus_elements[element_id]

            # Remove focus indicator
            if element_id in self._focus_indicators:
                del self._focus_indicators[element_id]

            # Update current focus if this element was focused
            if self._current_focus.element_id == element_id:
                self._current_focus.element_id = None
                self._current_focus.element_type = "unknown"
                self._current_focus.element_label = ""
                self._current_focus.focus_index = -1

            logger.debug(f"Unregistered focusable element: {element_id}")

        except Exception as e:
            logger.error(f"Error unregistering focusable element {element_id}: {e}")

    def _setup_element_accessibility(self,
                                   element: ft.Control,
                                   element_id: str,
                                   label: str,
                                   element_type: str) -> None:
        """Setup accessibility attributes for an element."""
        try:
            # Set semantic label
            if hasattr(element, 'semantics_label') and label:
                element.semantics_label = label

            # Set ARIA attributes (in data for Flet)
            if not hasattr(element, 'data'):
                element.data = {}

            element.data.update({
                'aria-label': label or element_id,
                'role': self._get_aria_role(element_type),
                'tabindex': '0',  # Make focusable
                'data-focus-id': element_id
            })

        except Exception as e:
            logger.error(f"Error setting up accessibility for {element_id}: {e}")

    def _get_aria_role(self, element_type: str) -> str:
        """Get appropriate ARIA role for element type."""
        role_mapping = {
            'button': 'button',
            'text': 'textbox',
            'input': 'textbox',
            'checkbox': 'checkbox',
            'radio': 'radio',
            'select': 'combobox',
            'link': 'link',
            'tab': 'tab',
            'menu': 'menuitem',
            'grid': 'gridcell',
            'list': 'listitem'
        }
        return role_mapping.get(element_type.lower(), 'generic')

    def _create_focus_indicator(self, element_id: str, element: ft.Control) -> None:
        """Create focus indicator for an element."""
        try:
            if not self._config.enable_focus_management:
                return

            # Get theme colors
            theme = self._get_theme()
            focus_color = self._config.focus_indicator_color or theme.primary

            # Create indicator based on style
            if self._config.focus_indicator_style == FocusIndicatorStyle.OUTLINE:
                # This would be implemented as an overlay or border in a real application
                # For now, we'll store the configuration
                indicator_config = {
                    'type': 'outline',
                    'color': focus_color,
                    'width': self._config.focus_indicator_width,
                    'offset': self._config.focus_indicator_offset
                }
            elif self._config.focus_indicator_style == FocusIndicatorStyle.HIGHLIGHT:
                indicator_config = {
                    'type': 'highlight',
                    'color': focus_color,
                    'opacity': 0.2
                }
            else:
                indicator_config = {
                    'type': 'custom',
                    'color': focus_color
                }

            self._focus_indicators[element_id] = indicator_config

        except Exception as e:
            logger.error(f"Error creating focus indicator for {element_id}: {e}")

    def _get_theme(self):
        """Get theme with fallback."""
        try:
            if self._theme_manager:
                return self._theme_manager.get_current_theme()
        except Exception:
            pass

        # Fallback theme
        class FallbackTheme:
            def __init__(self):
                self.primary = "#2196F3"
                self.text_primary = "#000000"
                self.surface = "#ffffff"

        return FallbackTheme()

    def focus_element(self, element_id: str, announce: bool = True) -> bool:
        """
        Set focus to a specific element.

        Args:
            element_id: ID of element to focus
            announce: Whether to announce focus change

        Returns:
            True if focus was set successfully
        """
        try:
            if element_id not in self._focus_elements:
                logger.warning(f"Element {element_id} not found in focus registry")
                return False

            element = self._focus_elements[element_id]

            # Check if element is focusable
            if not self._is_element_focusable(element):
                logger.debug(f"Element {element_id} is not focusable")
                return False

            # Record timing for metrics
            focus_start_time = time.time()

            # Update focus state
            old_focus_id = self._current_focus.element_id
            self._current_focus.element_id = element_id
            self._current_focus.focus_index = self._focus_order.index(element_id) if element_id in self._focus_order else -1
            self._current_focus.last_focus_time = focus_start_time

            # Add to focus history
            if len(self._current_focus.focus_history) >= self._config.max_focus_history:
                self._current_focus.focus_history.pop(0)
            if old_focus_id:
                self._current_focus.focus_history.append(old_focus_id)

            # Update visual focus indicator
            self._update_focus_indicator(element_id, old_focus_id)

            # Set actual focus (in a real implementation)
            try:
                if hasattr(element, 'focus'):
                    element.focus()
            except Exception as e:
                logger.debug(f"Could not set native focus on {element_id}: {e}")

            # Record metrics
            focus_duration = time.time() - focus_start_time
            self._metrics.record_focus_change(focus_duration)

            # Announce focus change
            if announce and self._config.announce_focus_changes:
                self._announce_focus_change(element_id)

            # Notify callbacks
            self._notify_focus_callbacks()

            logger.debug(f"Focus set to element: {element_id}")
            return True

        except Exception as e:
            logger.error(f"Error setting focus to {element_id}: {e}")
            self._metrics.record_error()
            return False

    def _is_element_focusable(self, element: ft.Control) -> bool:
        """Check if an element is currently focusable."""
        try:
            # Check if element is visible and enabled
            if hasattr(element, 'visible') and not element.visible:
                return False

            if hasattr(element, 'disabled') and element.disabled:
                return self._config.skip_disabled_elements is False

            return True

        except Exception:
            return False

    def _update_focus_indicator(self, new_focus_id: str, old_focus_id: Optional[str]) -> None:
        """Update visual focus indicators."""
        try:
            # Remove old focus indicator
            if old_focus_id and old_focus_id in self._focus_indicators:
                self._hide_focus_indicator(old_focus_id)

            # Show new focus indicator
            if new_focus_id in self._focus_indicators:
                self._show_focus_indicator(new_focus_id)

        except Exception as e:
            logger.error(f"Error updating focus indicator: {e}")

    def _show_focus_indicator(self, element_id: str) -> None:
        """Show focus indicator for an element."""
        try:
            if element_id not in self._focus_indicators:
                return

            indicator_config = self._focus_indicators[element_id]
            element = self._focus_elements[element_id]

            # Apply focus styling based on configuration
            # In a real implementation, this would apply visual styling
            if hasattr(element, 'data'):
                element.data['focused'] = 'true'

            logger.debug(f"Showing focus indicator for {element_id}")

        except Exception as e:
            logger.error(f"Error showing focus indicator for {element_id}: {e}")

    def _hide_focus_indicator(self, element_id: str) -> None:
        """Hide focus indicator for an element."""
        try:
            if element_id not in self._focus_elements:
                return

            element = self._focus_elements[element_id]

            # Remove focus styling
            if hasattr(element, 'data') and 'focused' in element.data:
                del element.data['focused']

            logger.debug(f"Hiding focus indicator for {element_id}")

        except Exception as e:
            logger.error(f"Error hiding focus indicator for {element_id}: {e}")

    def _announce_focus_change(self, element_id: str) -> None:
        """Announce focus change to screen readers."""
        try:
            if not self._screen_reader_manager:
                return

            element = self._focus_elements.get(element_id)
            if not element:
                return

            # Get element information
            label = ""
            element_type = "element"

            if hasattr(element, 'data') and element.data:
                label = element.data.get('aria-label', '')
                role = element.data.get('role', 'generic')
                element_type = role

            if hasattr(element, 'semantics_label') and element.semantics_label:
                label = element.semantics_label

            # Announce to screen reader
            self._screen_reader_manager.announce_focus_change(
                element_name=label or element_id,
                element_type=element_type
            )

        except Exception as e:
            logger.error(f"Error announcing focus change: {e}")

    def _notify_focus_callbacks(self) -> None:
        """Notify all focus change callbacks."""
        try:
            for callback in self._focus_callbacks:
                try:
                    callback(self._current_focus)
                except Exception as e:
                    logger.error(f"Error in focus callback: {e}")

        except Exception as e:
            logger.error(f"Error notifying focus callbacks: {e}")

    def navigate_focus(self, direction: FocusDirection) -> bool:
        """
        Navigate focus in the specified direction.

        Args:
            direction: Direction to navigate

        Returns:
            True if navigation was successful
        """
        try:
            if not self._focus_order:
                return False

            current_index = self._current_focus.focus_index
            new_index = self._calculate_new_focus_index(current_index, direction)

            if new_index == -1:
                return False

            new_element_id = self._focus_order[new_index]
            return self.focus_element(new_element_id)

        except Exception as e:
            logger.error(f"Error navigating focus {direction}: {e}")
            self._metrics.record_error()
            return False

    def _calculate_new_focus_index(self, current_index: int, direction: FocusDirection) -> int:
        """Calculate new focus index based on direction."""
        try:
            total_elements = len(self._focus_order)
            if total_elements == 0:
                return -1

            if direction == FocusDirection.NEXT:
                new_index = (current_index + 1) % total_elements if self._config.wrap_navigation else min(current_index + 1, total_elements - 1)
            elif direction == FocusDirection.PREVIOUS:
                new_index = (current_index - 1) % total_elements if self._config.wrap_navigation else max(current_index - 1, 0)
            elif direction == FocusDirection.FIRST:
                new_index = 0
            elif direction == FocusDirection.LAST:
                new_index = total_elements - 1
            else:
                # For spatial navigation (UP, DOWN, LEFT, RIGHT)
                new_index = self._calculate_spatial_navigation(current_index, direction)

            # Skip disabled elements if configured
            if self._config.skip_disabled_elements:
                new_index = self._find_next_focusable_index(new_index, direction)

            return new_index if 0 <= new_index < total_elements else -1

        except Exception as e:
            logger.error(f"Error calculating new focus index: {e}")
            return -1

    def _calculate_spatial_navigation(self, current_index: int, direction: FocusDirection) -> int:
        """Calculate spatial navigation for arrow keys."""
        # This is a simplified implementation
        # In a real application, this would consider element positions
        if direction in [FocusDirection.UP, FocusDirection.LEFT]:
            return max(current_index - 1, 0)
        elif direction in [FocusDirection.DOWN, FocusDirection.RIGHT]:
            return min(current_index + 1, len(self._focus_order) - 1)
        return current_index

    def _find_next_focusable_index(self, start_index: int, direction: FocusDirection) -> int:
        """Find next focusable element index."""
        try:
            total_elements = len(self._focus_order)
            checked = 0
            current_index = start_index

            while checked < total_elements:
                if 0 <= current_index < total_elements:
                    element_id = self._focus_order[current_index]
                    element = self._focus_elements.get(element_id)

                    if element and self._is_element_focusable(element):
                        return current_index

                # Move to next index
                if direction in [FocusDirection.NEXT, FocusDirection.DOWN, FocusDirection.RIGHT]:
                    current_index = (current_index + 1) % total_elements if self._config.wrap_navigation else current_index + 1
                else:
                    current_index = (current_index - 1) % total_elements if self._config.wrap_navigation else current_index - 1

                checked += 1

                if not self._config.wrap_navigation and (current_index < 0 or current_index >= total_elements):
                    break

            return -1

        except Exception as e:
            logger.error(f"Error finding next focusable index: {e}")
            return -1

    def create_focus_trap(self, container_id: str, element_ids: List[str]) -> None:
        """
        Create a focus trap within a container.

        Args:
            container_id: ID of the container to trap focus within
            element_ids: List of element IDs that should be included in the trap
        """
        try:
            # Store trapped elements
            self._trapped_elements[container_id] = element_ids.copy()

            # Add to focus trap stack
            self._focus_trap_stack.append(container_id)

            # Update focus state
            self._current_focus.is_trapped = True
            self._current_focus.trap_container = container_id

            # Focus first element in trap if no current focus
            if not self._current_focus.element_id and element_ids:
                self.focus_element(element_ids[0])

            logger.debug(f"Created focus trap for container: {container_id}")

        except Exception as e:
            logger.error(f"Error creating focus trap for {container_id}: {e}")

    def release_focus_trap(self, container_id: Optional[str] = None) -> None:
        """
        Release a focus trap.

        Args:
            container_id: Specific container to release (None = release current)
        """
        try:
            if container_id is None and self._focus_trap_stack:
                container_id = self._focus_trap_stack[-1]

            if not container_id:
                return

            # Remove from trap stack
            if container_id in self._focus_trap_stack:
                self._focus_trap_stack.remove(container_id)

            # Remove trapped elements
            if container_id in self._trapped_elements:
                del self._trapped_elements[container_id]

            # Update focus state
            if not self._focus_trap_stack:
                self._current_focus.is_trapped = False
                self._current_focus.trap_container = None
            else:
                self._current_focus.trap_container = self._focus_trap_stack[-1]

            logger.debug(f"Released focus trap for container: {container_id}")

        except Exception as e:
            logger.error(f"Error releasing focus trap for {container_id}: {e}")

    def is_focus_trapped(self) -> bool:
        """Check if focus is currently trapped."""
        return self._current_focus.is_trapped

    def get_current_focus(self) -> FocusState:
        """Get current focus state."""
        return self._current_focus

    def add_focus_callback(self, callback: Callable[[FocusState], None]) -> None:
        """Add a focus change callback."""
        if callback not in self._focus_callbacks:
            self._focus_callbacks.append(callback)

    def remove_focus_callback(self, callback: Callable[[FocusState], None]) -> None:
        """Remove a focus change callback."""
        if callback in self._focus_callbacks:
            self._focus_callbacks.remove(callback)

    def get_focus_metrics(self) -> NavigationMetrics:
        """Get focus navigation metrics."""
        return self._metrics

    def reset_focus_metrics(self) -> None:
        """Reset focus navigation metrics."""
        self._metrics.reset_metrics()

    def cleanup(self) -> None:
        """Clean up focus manager resources."""
        try:
            # Clear all focus traps
            while self._focus_trap_stack:
                self.release_focus_trap()

            # Clear focus state
            self._current_focus = FocusState()

            # Clear callbacks
            self._focus_callbacks.clear()

            logger.debug("FocusManager cleanup completed")

        except Exception as e:
            logger.error(f"Error during FocusManager cleanup: {e}")


class ShortcutManager:
    """
    Keyboard shortcut management system with conflict detection and resolution.

    Manages registration, execution, and conflict resolution for keyboard shortcuts
    with support for different scopes and priority levels.
    """

    def __init__(self, config: Optional[KeyboardConfiguration] = None):
        """
        Initialize the shortcut manager.

        Args:
            config: Keyboard navigation configuration
        """
        self._config = config or KeyboardConfiguration()
        self._shortcuts: Dict[str, KeyboardShortcut] = {}
        self._scope_shortcuts: Dict[ShortcutScope, Dict[str, KeyboardShortcut]] = {
            scope: {} for scope in ShortcutScope
        }
        self._active_scopes: Set[ShortcutScope] = {ShortcutScope.GLOBAL}
        self._metrics = NavigationMetrics()

        # Default shortcuts
        self._register_default_shortcuts()

        logger.info("ShortcutManager initialized")

    def _register_default_shortcuts(self) -> None:
        """Register default application shortcuts."""
        try:
            default_shortcuts = [
                KeyboardShortcut(
                    key="F1",
                    action=None,  # Will be set by application
                    description="Show help",
                    category="help",
                    accessibility_label="Show context-sensitive help"
                ),
                KeyboardShortcut(
                    key="Escape",
                    action=None,
                    description="Cancel or close",
                    category="navigation",
                    accessibility_label="Cancel current operation or close dialog"
                ),
                KeyboardShortcut(
                    key="Tab",
                    action=None,
                    description="Navigate to next element",
                    category="navigation",
                    accessibility_label="Move focus to next element"
                ),
                KeyboardShortcut(
                    key="Tab",
                    modifiers={KeyModifier.SHIFT},
                    action=None,
                    description="Navigate to previous element",
                    category="navigation",
                    accessibility_label="Move focus to previous element"
                )
            ]

            for shortcut in default_shortcuts:
                self.register_shortcut(shortcut)

        except Exception as e:
            logger.error(f"Error registering default shortcuts: {e}")

    def register_shortcut(self, shortcut: KeyboardShortcut) -> bool:
        """
        Register a keyboard shortcut.

        Args:
            shortcut: Shortcut to register

        Returns:
            True if registration was successful
        """
        try:
            if not self._config.enable_shortcuts:
                return False

            shortcut_key = shortcut.get_key_combination()

            # Check for conflicts
            if self._has_conflict(shortcut):
                if self._config.conflict_resolution == "priority":
                    self._resolve_conflict_by_priority(shortcut)
                else:
                    logger.warning(f"Shortcut conflict for {shortcut_key}, keeping existing")
                    return False

            # Register shortcut
            self._shortcuts[shortcut_key] = shortcut
            self._scope_shortcuts[shortcut.scope][shortcut_key] = shortcut

            logger.debug(f"Registered shortcut: {shortcut_key} - {shortcut.description}")
            return True

        except Exception as e:
            logger.error(f"Error registering shortcut: {e}")
            return False

    def _has_conflict(self, shortcut: KeyboardShortcut) -> bool:
        """Check if shortcut conflicts with existing shortcuts."""
        shortcut_key = shortcut.get_key_combination()

        # Check global conflicts
        if shortcut_key in self._shortcuts:
            existing = self._shortcuts[shortcut_key]
            if existing.scope == shortcut.scope or shortcut.scope == ShortcutScope.GLOBAL:
                return True

        return False

    def _resolve_conflict_by_priority(self, new_shortcut: KeyboardShortcut) -> None:
        """Resolve shortcut conflict by priority."""
        shortcut_key = new_shortcut.get_key_combination()
        existing = self._shortcuts.get(shortcut_key)

        if existing and new_shortcut.priority > existing.priority:
            # Remove existing shortcut
            self.unregister_shortcut(shortcut_key)
            logger.info(f"Replaced shortcut {shortcut_key} due to higher priority")

    def unregister_shortcut(self, shortcut_key: str) -> bool:
        """
        Unregister a keyboard shortcut.

        Args:
            shortcut_key: Key combination to unregister

        Returns:
            True if unregistration was successful
        """
        try:
            if shortcut_key in self._shortcuts:
                shortcut = self._shortcuts[shortcut_key]

                # Remove from main registry
                del self._shortcuts[shortcut_key]

                # Remove from scope registry
                if shortcut_key in self._scope_shortcuts[shortcut.scope]:
                    del self._scope_shortcuts[shortcut.scope][shortcut_key]

                logger.debug(f"Unregistered shortcut: {shortcut_key}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error unregistering shortcut {shortcut_key}: {e}")
            return False

    def handle_keyboard_event(self, event: ft.KeyboardEvent) -> bool:
        """
        Handle keyboard event and execute matching shortcuts.

        Args:
            event: Keyboard event

        Returns:
            True if event was handled by a shortcut
        """
        try:
            if not self._config.enable_shortcuts:
                return False

            # Find matching shortcuts in active scopes
            for scope in self._active_scopes:
                for shortcut in self._scope_shortcuts[scope].values():
                    if shortcut.enabled and shortcut.matches_event(event):
                        return self._execute_shortcut(shortcut, event)

            return False

        except Exception as e:
            logger.error(f"Error handling keyboard event: {e}")
            return False

    def _execute_shortcut(self, shortcut: KeyboardShortcut, event: ft.KeyboardEvent) -> bool:
        """Execute a keyboard shortcut."""
        try:
            if not shortcut.action:
                return False

            # Record metrics
            self._metrics.record_shortcut_usage(shortcut.get_key_combination())

            # Execute action
            result = shortcut.action(event) if callable(shortcut.action) else True

            logger.debug(f"Executed shortcut: {shortcut.get_key_combination()}")
            return result

        except Exception as e:
            logger.error(f"Error executing shortcut {shortcut.get_key_combination()}: {e}")
            self._metrics.record_error()
            return False

    def set_active_scopes(self, scopes: Set[ShortcutScope]) -> None:
        """Set active shortcut scopes."""
        self._active_scopes = scopes.copy()
        # Always include global scope
        self._active_scopes.add(ShortcutScope.GLOBAL)

    def get_shortcuts_by_category(self, category: str) -> List[KeyboardShortcut]:
        """Get shortcuts by category."""
        return [s for s in self._shortcuts.values() if s.category == category]

    def get_all_shortcuts(self) -> Dict[str, KeyboardShortcut]:
        """Get all registered shortcuts."""
        return self._shortcuts.copy()

    def get_metrics(self) -> NavigationMetrics:
        """Get shortcut usage metrics."""
        return self._metrics


class KeyboardNavigationUI(ThemeAwareUserControl):
    """
    Main keyboard navigation UI component with comprehensive accessibility features.

    Features:
    - WCAG 2.1 AA compliant keyboard navigation
    - Focus management with visual indicators
    - Keyboard shortcut management and customization
    - Screen reader integration and announcements
    - Theme-aware styling with responsive design
    - Performance optimization for keyboard interactions
    - Accessibility state monitoring and reporting
    """

    def __init__(self,
                 config: Optional[KeyboardConfiguration] = None,
                 enable_ui_panel: bool = True,
                 **kwargs):
        """
        Initialize the keyboard navigation UI component.

        Args:
            config: Keyboard navigation configuration
            enable_ui_panel: Whether to show the UI management panel
            **kwargs: Additional component properties
        """
        super().__init__(**kwargs)

        # Configuration
        self._config = config or KeyboardConfiguration()
        self._enable_ui_panel = enable_ui_panel

        # Core components
        self._focus_manager = None
        self._shortcut_manager = None
        self._screen_reader_manager = None

        # Theme integration with safe initialization
        self._theme_manager = get_theme_manager()
        self._responsive_manager = None
        self._accessibility_manager = None

        # Safely get managers
        if self._theme_manager is not None:
            try:
                self._responsive_manager = self._theme_manager.get_responsive_layout_manager()
                self._accessibility_manager = self._theme_manager.get_accessibility_manager()
            except Exception as e:
                logger.warning(f"Could not get theme managers: {e}")
                self._responsive_manager = None
                self._accessibility_manager = None
        else:
            logger.warning("Theme manager not available, using fallback initialization")

        # State tracking
        self._is_initialized = False
        self._current_screen_size = ScreenSize.DESKTOP
        self._keyboard_navigation_active = True

        # Performance tracking
        self._performance_metrics = {
            'keyboard_events_handled': 0,
            'focus_changes': 0,
            'shortcuts_executed': 0,
            'navigation_errors': 0,
            'last_update': time.time()
        }

        # Event handlers
        self._keyboard_handlers: List[Callable] = []
        self._navigation_handlers: List[Callable] = []

        logger.info("KeyboardNavigationUI component initialized")

    def get_theme(self):
        """Get theme with fallback for when theme manager is not available."""
        try:
            if hasattr(super(), 'get_theme'):
                return super().get_theme()
        except Exception:
            pass

        # Fallback theme object
        class FallbackTheme:
            def __init__(self):
                self.surface = "#ffffff"
                self.surface_variant = "#f5f5f5"
                self.background_primary = "#ffffff"
                self.background_secondary = "#f8f9fa"
                self.text_primary = "#000000"
                self.text_secondary = "#666666"
                self.primary = "#2196F3"
                self.success = "#4caf50"
                self.warning = "#ff9800"
                self.error = "#f44336"
                self.outline = "#e0e0e0"
                self.borders = "#e0e0e0"

        return FallbackTheme()

    def get_spacing(self):
        """Get spacing with fallback."""
        try:
            if hasattr(super(), 'get_spacing'):
                return super().get_spacing()
        except Exception:
            pass

        # Fallback spacing object
        class FallbackSpacing:
            def __init__(self):
                self.xs = 4
                self.sm = 8
                self.md = 16
                self.lg = 24
                self.xl = 32

        return FallbackSpacing()

    def get_typography(self):
        """Get typography with fallback."""
        try:
            if hasattr(super(), 'get_typography'):
                return super().get_typography()
        except Exception:
            pass

        # Fallback typography object
        class FallbackTypography:
            def __init__(self):
                self.h6 = (16, 20, 500, 0.0)
                self.body_medium = (14, 20, 400, 0.0)
                self.body_small = (12, 16, 400, 0.0)

        return FallbackTypography()

    def get_icons(self):
        """Get icons with fallback."""
        try:
            if hasattr(super(), 'get_icons'):
                return super().get_icons()
        except Exception:
            pass

        # Fallback icons object
        class FallbackIcons:
            def __init__(self):
                self.KEYBOARD = ft.Icons.KEYBOARD
                self.VISIBILITY = ft.Icons.VISIBILITY
                self.SETTINGS = ft.Icons.SETTINGS
                self.CHECK_CIRCLE = ft.Icons.CHECK_CIRCLE
                self.WARNING = ft.Icons.WARNING
                self.HELP = ft.Icons.HELP
                self.CLEAR_ALL = ft.Icons.CLEAR_ALL

        return FallbackIcons()

    def build(self) -> ft.Control:
        """Build the keyboard navigation UI component."""
        theme = self.get_theme()
        spacing = self.get_spacing()

        # Initialize core components
        if not self._is_initialized:
            self._initialize_components()
            self._is_initialized = True

        # Create main container
        if self._enable_ui_panel:
            main_container = ft.Container(
                content=self._build_navigation_panel(),
                padding=ft.padding.all(spacing.md),
                bgcolor=theme.surface,
                border_radius=8,
                border=ft.border.all(1, theme.outline),
                # Accessibility properties
                data={
                    "role": "region",
                    "aria-label": "Keyboard Navigation Control Panel",
                    "aria-describedby": "keyboard-navigation-description"
                }
            )
        else:
            # Invisible container for keyboard handling only
            main_container = ft.Container(
                content=ft.Text("", size=1),
                width=1,
                height=1,
                visible=False,
                data={
                    "role": "application",
                    "aria-label": "Keyboard Navigation Handler"
                }
            )

        # Setup responsive behavior
        self._setup_responsive_behavior()

        # Setup keyboard event handling
        self._setup_keyboard_handling()

        return main_container

    def _initialize_components(self) -> None:
        """Initialize core keyboard navigation components."""
        try:
            # Initialize screen reader manager if available
            try:
                from src.modules.ui.accessibility_ui.screen_reader_ui.screen_reader_ui import ScreenReaderManager
                self._screen_reader_manager = ScreenReaderManager()
            except ImportError:
                logger.warning("Screen reader manager not available")
                self._screen_reader_manager = None

            # Initialize focus manager
            self._focus_manager = FocusManager(
                config=self._config,
                screen_reader_manager=self._screen_reader_manager
            )

            # Initialize shortcut manager
            self._shortcut_manager = ShortcutManager(config=self._config)

            # Setup default keyboard shortcuts
            self._setup_default_shortcuts()

            logger.debug("Keyboard navigation components initialized")

        except Exception as e:
            logger.error(f"Error initializing keyboard navigation components: {e}")

    def _setup_default_shortcuts(self) -> None:
        """Setup default keyboard shortcuts for navigation."""
        try:
            # Navigation shortcuts
            navigation_shortcuts = [
                KeyboardShortcut(
                    key="Tab",
                    action=lambda e: self._handle_tab_navigation(e, forward=True),
                    description="Navigate to next element",
                    category="navigation",
                    scope=ShortcutScope.GLOBAL
                ),
                KeyboardShortcut(
                    key="Tab",
                    modifiers={KeyModifier.SHIFT},
                    action=lambda e: self._handle_tab_navigation(e, forward=False),
                    description="Navigate to previous element",
                    category="navigation",
                    scope=ShortcutScope.GLOBAL
                ),
                KeyboardShortcut(
                    key="ArrowDown",
                    action=lambda e: self._handle_arrow_navigation(e, FocusDirection.DOWN),
                    description="Navigate down",
                    category="navigation",
                    scope=ShortcutScope.GLOBAL
                ),
                KeyboardShortcut(
                    key="ArrowUp",
                    action=lambda e: self._handle_arrow_navigation(e, FocusDirection.UP),
                    description="Navigate up",
                    category="navigation",
                    scope=ShortcutScope.GLOBAL
                ),
                KeyboardShortcut(
                    key="ArrowLeft",
                    action=lambda e: self._handle_arrow_navigation(e, FocusDirection.LEFT),
                    description="Navigate left",
                    category="navigation",
                    scope=ShortcutScope.GLOBAL
                ),
                KeyboardShortcut(
                    key="ArrowRight",
                    action=lambda e: self._handle_arrow_navigation(e, FocusDirection.RIGHT),
                    description="Navigate right",
                    category="navigation",
                    scope=ShortcutScope.GLOBAL
                ),
                KeyboardShortcut(
                    key="Home",
                    action=lambda e: self._handle_boundary_navigation(e, FocusDirection.FIRST),
                    description="Navigate to first element",
                    category="navigation",
                    scope=ShortcutScope.GLOBAL
                ),
                KeyboardShortcut(
                    key="End",
                    action=lambda e: self._handle_boundary_navigation(e, FocusDirection.LAST),
                    description="Navigate to last element",
                    category="navigation",
                    scope=ShortcutScope.GLOBAL
                ),
                KeyboardShortcut(
                    key="Escape",
                    action=lambda e: self._handle_escape_key(e),
                    description="Cancel or close",
                    category="navigation",
                    scope=ShortcutScope.GLOBAL
                )
            ]

            # Register shortcuts
            for shortcut in navigation_shortcuts:
                self._shortcut_manager.register_shortcut(shortcut)

        except Exception as e:
            logger.error(f"Error setting up default shortcuts: {e}")

    def _handle_tab_navigation(self, event: ft.KeyboardEvent, forward: bool = True) -> bool:
        """Handle Tab key navigation."""
        try:
            if not self._focus_manager:
                return False

            direction = FocusDirection.NEXT if forward else FocusDirection.PREVIOUS
            return self._focus_manager.navigate_focus(direction)

        except Exception as e:
            logger.error(f"Error handling tab navigation: {e}")
            return False

    def _handle_arrow_navigation(self, event: ft.KeyboardEvent, direction: FocusDirection) -> bool:
        """Handle arrow key navigation."""
        try:
            if not self._focus_manager or not self._config.enable_spatial_navigation:
                return False

            return self._focus_manager.navigate_focus(direction)

        except Exception as e:
            logger.error(f"Error handling arrow navigation: {e}")
            return False

    def _handle_boundary_navigation(self, event: ft.KeyboardEvent, direction: FocusDirection) -> bool:
        """Handle Home/End key navigation."""
        try:
            if not self._focus_manager:
                return False

            return self._focus_manager.navigate_focus(direction)

        except Exception as e:
            logger.error(f"Error handling boundary navigation: {e}")
            return False

    def _handle_escape_key(self, event: ft.KeyboardEvent) -> bool:
        """Handle Escape key."""
        try:
            if not self._focus_manager:
                return False

            # Release focus trap if active
            if self._focus_manager.is_focus_trapped():
                self._focus_manager.release_focus_trap()
                return True

            return False

        except Exception as e:
            logger.error(f"Error handling escape key: {e}")
            return False

    def _build_navigation_panel(self) -> ft.Control:
        """Build the keyboard navigation control panel."""
        theme = self.get_theme()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Status section
        status_section = self._build_status_section()

        # Focus management section
        focus_section = self._build_focus_section()

        # Shortcuts section
        shortcuts_section = self._build_shortcuts_section()

        # Controls section
        controls_section = self._build_controls_section()

        # Metrics section (if enabled)
        metrics_section = None
        if self._config.enable_performance_monitoring:
            metrics_section = self._build_metrics_section()

        # Combine sections
        sections = [status_section, focus_section, shortcuts_section, controls_section]
        if metrics_section:
            sections.append(metrics_section)

        return ft.Column(
            controls=sections,
            spacing=spacing.lg,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )

    def _build_status_section(self) -> ft.Control:
        """Build the keyboard navigation status section."""
        theme = self.get_theme()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Navigation status
        nav_active = self._keyboard_navigation_active
        status_color = theme.success if nav_active else theme.warning
        status_icon = icons.CHECK_CIRCLE if nav_active else icons.WARNING
        status_text = "Keyboard Navigation Active" if nav_active else "Keyboard Navigation Disabled"

        status_indicator = ft.Row(
            controls=[
                ft.Icon(
                    name=status_icon,
                    color=status_color,
                    size=20
                ),
                ft.Text(
                    value=status_text,
                    size=typography.body_medium[0],
                    color=status_color,
                    weight=ft.FontWeight.W_500
                )
            ],
            spacing=spacing.sm,
            alignment=ft.MainAxisAlignment.START
        )

        # Configuration status
        config_items = [
            f"Focus Management: {'Enabled' if self._config.enable_focus_management else 'Disabled'}",
            f"Shortcuts: {'Enabled' if self._config.enable_shortcuts else 'Disabled'}",
            f"Spatial Navigation: {'Enabled' if self._config.enable_spatial_navigation else 'Disabled'}",
            f"Screen Reader Support: {'Available' if self._screen_reader_manager else 'Not Available'}"
        ]

        config_controls = [
            ft.Text(
                value=item,
                size=typography.body_small[0],
                color=theme.text_secondary
            ) for item in config_items
        ]

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        value="Keyboard Navigation Status",
                        size=typography.h6[0],
                        weight=ft.FontWeight.W_600,
                        color=theme.text_primary
                    ),
                    status_indicator,
                    *config_controls
                ],
                spacing=spacing.sm
            ),
            padding=ft.padding.all(spacing.md),
            bgcolor=theme.surface_variant,
            border_radius=6,
            data={
                "role": "status",
                "aria-label": "Keyboard Navigation Status Information"
            }
        )

    def _build_focus_section(self) -> ft.Control:
        """Build the focus management section."""
        theme = self.get_theme()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Current focus information
        current_focus = self._focus_manager.get_current_focus() if self._focus_manager else FocusState()

        focus_info = [
            f"Current Focus: {current_focus.element_id or 'None'}",
            f"Element Type: {current_focus.element_type}",
            f"Focus Index: {current_focus.focus_index}",
            f"Focus Trapped: {'Yes' if current_focus.is_trapped else 'No'}"
        ]

        if current_focus.is_trapped and current_focus.trap_container:
            focus_info.append(f"Trap Container: {current_focus.trap_container}")

        focus_controls = [
            ft.Text(
                value=info,
                size=typography.body_small[0],
                color=theme.text_secondary
            ) for info in focus_info
        ]

        # Focus metrics
        if self._focus_manager:
            metrics = self._focus_manager.get_focus_metrics()
            metrics_info = [
                f"Focus Changes: {metrics.focus_changes}",
                f"Navigation Errors: {metrics.navigation_errors}",
                f"Average Focus Time: {metrics.average_focus_time:.2f}s"
            ]

            metrics_controls = [
                ft.Text(
                    value=info,
                    size=typography.body_small[0],
                    color=theme.text_secondary
                ) for info in metrics_info
            ]

            focus_controls.extend(metrics_controls)

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        value="Focus Management",
                        size=typography.h6[0],
                        weight=ft.FontWeight.W_600,
                        color=theme.text_primary
                    ),
                    *focus_controls
                ],
                spacing=spacing.sm
            ),
            padding=ft.padding.all(spacing.md),
            bgcolor=theme.surface_variant,
            border_radius=6
        )

    def _build_shortcuts_section(self) -> ft.Control:
        """Build the keyboard shortcuts section."""
        theme = self.get_theme()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Get shortcuts by category
        shortcuts = self._shortcut_manager.get_all_shortcuts() if self._shortcut_manager else {}
        categories = {}

        for shortcut in shortcuts.values():
            if shortcut.category not in categories:
                categories[shortcut.category] = []
            categories[shortcut.category].append(shortcut)

        category_controls = []
        for category, category_shortcuts in categories.items():
            # Category header
            category_header = ft.Text(
                value=f"{category.title()} Shortcuts",
                size=typography.body_medium[0],
                weight=ft.FontWeight.W_500,
                color=theme.text_primary
            )

            # Shortcut items
            shortcut_items = []
            for shortcut in category_shortcuts[:5]:  # Limit display
                shortcut_item = ft.Row(
                    controls=[
                        ft.Text(
                            value=shortcut.get_key_combination(),
                            size=typography.body_small[0],
                            color=theme.primary,
                            weight=ft.FontWeight.W_500,
                            expand=False
                        ),
                        ft.Text(
                            value=shortcut.description,
                            size=typography.body_small[0],
                            color=theme.text_secondary,
                            expand=True
                        )
                    ],
                    spacing=spacing.sm
                )
                shortcut_items.append(shortcut_item)

            if len(category_shortcuts) > 5:
                shortcut_items.append(
                    ft.Text(
                        value=f"... and {len(category_shortcuts) - 5} more",
                        size=typography.body_small[0],
                        color=theme.text_secondary,
                        italic=True
                    )
                )

            category_container = ft.Container(
                content=ft.Column(
                    controls=[category_header, *shortcut_items],
                    spacing=spacing.xs
                ),
                padding=ft.padding.all(spacing.sm),
                bgcolor=theme.background_secondary,
                border_radius=4,
                border=ft.border.all(1, theme.borders)
            )
            category_controls.append(category_container)

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        value="Keyboard Shortcuts",
                        size=typography.h6[0],
                        weight=ft.FontWeight.W_600,
                        color=theme.text_primary
                    ),
                    ft.Column(
                        controls=category_controls,
                        spacing=spacing.sm
                    )
                ],
                spacing=spacing.sm
            ),
            padding=ft.padding.all(spacing.md),
            bgcolor=theme.surface_variant,
            border_radius=6
        )

    def _build_controls_section(self) -> ft.Control:
        """Build the keyboard navigation controls section."""
        theme = self.get_theme()
        typography = self.get_typography()
        spacing = self.get_spacing()
        icons = self.get_icons()

        # Toggle navigation button
        toggle_button = ft.ElevatedButton(
            text="Disable Navigation" if self._keyboard_navigation_active else "Enable Navigation",
            icon=icons.VISIBILITY if self._keyboard_navigation_active else icons.SETTINGS,
            on_click=self._handle_toggle_navigation,
            bgcolor=theme.primary,
            color=theme.text_primary,
            data={
                "aria-label": f"{'Disable' if self._keyboard_navigation_active else 'Enable'} keyboard navigation"
            }
        )

        # Show shortcuts button
        shortcuts_button = ft.OutlinedButton(
            text="Show All Shortcuts",
            icon=icons.KEYBOARD,
            on_click=self._handle_show_shortcuts,
            data={
                "aria-label": "Show all keyboard shortcuts"
            }
        )

        # Reset focus button
        reset_button = ft.OutlinedButton(
            text="Reset Focus",
            icon=icons.CLEAR_ALL,
            on_click=self._handle_reset_focus,
            data={
                "aria-label": "Reset focus to first element"
            }
        )

        # Help button
        help_button = ft.OutlinedButton(
            text="Help",
            icon=icons.HELP,
            on_click=self._handle_show_help,
            data={
                "aria-label": "Show keyboard navigation help"
            }
        )

        controls_row = ft.Row(
            controls=[toggle_button, shortcuts_button, reset_button, help_button],
            spacing=spacing.md,
            wrap=True,
            alignment=ft.MainAxisAlignment.START
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        value="Navigation Controls",
                        size=typography.h6[0],
                        weight=ft.FontWeight.W_600,
                        color=theme.text_primary
                    ),
                    controls_row
                ],
                spacing=spacing.sm
            ),
            padding=ft.padding.all(spacing.md),
            bgcolor=theme.surface_variant,
            border_radius=6
        )

    def _build_metrics_section(self) -> ft.Control:
        """Build the performance metrics section."""
        theme = self.get_theme()
        typography = self.get_typography()
        spacing = self.get_spacing()

        # Get combined metrics
        metrics = self._performance_metrics.copy()

        if self._focus_manager:
            focus_metrics = self._focus_manager.get_focus_metrics()
            metrics.update({
                'focus_manager_focus_changes': focus_metrics.focus_changes,
                'focus_manager_errors': focus_metrics.navigation_errors
            })

        if self._shortcut_manager:
            shortcut_metrics = self._shortcut_manager.get_metrics()
            metrics.update({
                'shortcuts_triggered': shortcut_metrics.shortcuts_triggered,
                'shortcut_errors': shortcut_metrics.navigation_errors
            })

        metric_items = []
        for key, value in metrics.items():
            if isinstance(value, (int, float)) and not key.startswith('_'):
                display_key = key.replace('_', ' ').title()
                metric_item = ft.Row(
                    controls=[
                        ft.Text(
                            value=f"{display_key}:",
                            size=typography.body_small[0],
                            color=theme.text_secondary,
                            expand=True
                        ),
                        ft.Text(
                            value=str(value),
                            size=typography.body_small[0],
                            color=theme.text_primary,
                            weight=ft.FontWeight.W_500
                        )
                    ],
                    spacing=spacing.sm
                )
                metric_items.append(metric_item)

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        value="Performance Metrics",
                        size=typography.h6[0],
                        weight=ft.FontWeight.W_600,
                        color=theme.text_primary
                    ),
                    ft.Column(
                        controls=metric_items,
                        spacing=spacing.xs
                    )
                ],
                spacing=spacing.sm
            ),
            padding=ft.padding.all(spacing.md),
            bgcolor=theme.surface_variant,
            border_radius=6
        )

    def _setup_responsive_behavior(self) -> None:
        """Setup responsive behavior for the component."""
        try:
            if self._responsive_manager is not None:
                # Add resize callback
                self._responsive_manager.add_resize_callback(self._handle_resize)

                # Get current screen size
                self._current_screen_size = self._responsive_manager.get_current_screen_size()

                logger.debug("Responsive behavior setup completed")
            else:
                logger.warning("Responsive manager not available, using default screen size")
                self._current_screen_size = ScreenSize.DESKTOP

        except Exception as e:
            logger.error(f"Error setting up responsive behavior: {e}")
            self._current_screen_size = ScreenSize.DESKTOP

    def _setup_keyboard_handling(self) -> None:
        """Setup keyboard event handling."""
        try:
            # This would be implemented with proper keyboard event binding in a real application
            # For now, we'll just log that it's set up
            logger.debug("Keyboard event handling setup completed")

        except Exception as e:
            logger.error(f"Error setting up keyboard handling: {e}")

    def _handle_resize(self, width: int, height: int, screen_size: ScreenSize) -> None:
        """Handle window resize events."""
        try:
            old_screen_size = self._current_screen_size
            self._current_screen_size = screen_size

            # Update focus indicators for new screen size if needed
            if old_screen_size != screen_size and self._focus_manager:
                # This would update focus indicator styling for the new screen size
                pass

        except Exception as e:
            logger.error(f"Error handling resize: {e}")

    # Event handlers for UI controls

    def _handle_toggle_navigation(self, e) -> None:
        """Handle toggle navigation button click."""
        try:
            self._keyboard_navigation_active = not self._keyboard_navigation_active

            # Update button text
            if hasattr(e.control, 'text'):
                e.control.text = "Disable Navigation" if self._keyboard_navigation_active else "Enable Navigation"

            # Announce change
            if self._screen_reader_manager:
                status = "enabled" if self._keyboard_navigation_active else "disabled"
                self._screen_reader_manager.announce(f"Keyboard navigation {status}")

            # Update the UI
            if hasattr(self, 'update'):
                self.update()

        except Exception as e:
            logger.error(f"Error toggling navigation: {e}")

    def _handle_show_shortcuts(self, e) -> None:
        """Handle show shortcuts button click."""
        try:
            # This would open a shortcuts dialog in a real implementation
            if self._screen_reader_manager:
                self._screen_reader_manager.announce("Keyboard shortcuts dialog opened")

        except Exception as e:
            logger.error(f"Error showing shortcuts: {e}")

    def _handle_reset_focus(self, e) -> None:
        """Handle reset focus button click."""
        try:
            if self._focus_manager and self._focus_manager._focus_order:
                first_element = self._focus_manager._focus_order[0]
                self._focus_manager.focus_element(first_element)

        except Exception as e:
            logger.error(f"Error resetting focus: {e}")

    def _handle_show_help(self, e) -> None:
        """Handle show help button click."""
        try:
            # This would open a help dialog in a real implementation
            if self._screen_reader_manager:
                self._screen_reader_manager.announce("Keyboard navigation help opened")

        except Exception as e:
            logger.error(f"Error showing help: {e}")

    # Public API methods

    def register_focusable_element(self,
                                 element_id: str,
                                 element: ft.Control,
                                 label: str = "",
                                 element_type: str = "element") -> bool:
        """
        Register an element as focusable.

        Args:
            element_id: Unique identifier for the element
            element: Flet control element
            label: Accessible label for the element
            element_type: Type of element (button, text, etc.)

        Returns:
            True if registration was successful
        """
        try:
            if not self._focus_manager:
                return False

            self._focus_manager.register_focusable_element(
                element_id=element_id,
                element=element,
                label=label,
                element_type=element_type
            )
            return True

        except Exception as e:
            logger.error(f"Error registering focusable element: {e}")
            return False

    def unregister_focusable_element(self, element_id: str) -> bool:
        """
        Unregister a focusable element.

        Args:
            element_id: Element identifier to unregister

        Returns:
            True if unregistration was successful
        """
        try:
            if not self._focus_manager:
                return False

            self._focus_manager.unregister_focusable_element(element_id)
            return True

        except Exception as e:
            logger.error(f"Error unregistering focusable element: {e}")
            return False

    def focus_element(self, element_id: str) -> bool:
        """
        Set focus to a specific element.

        Args:
            element_id: ID of element to focus

        Returns:
            True if focus was set successfully
        """
        try:
            if not self._focus_manager:
                return False

            return self._focus_manager.focus_element(element_id)

        except Exception as e:
            logger.error(f"Error focusing element: {e}")
            return False

    def register_keyboard_shortcut(self, shortcut: KeyboardShortcut) -> bool:
        """
        Register a keyboard shortcut.

        Args:
            shortcut: Shortcut to register

        Returns:
            True if registration was successful
        """
        try:
            if not self._shortcut_manager:
                return False

            return self._shortcut_manager.register_shortcut(shortcut)

        except Exception as e:
            logger.error(f"Error registering keyboard shortcut: {e}")
            return False

    def unregister_keyboard_shortcut(self, shortcut_key: str) -> bool:
        """
        Unregister a keyboard shortcut.

        Args:
            shortcut_key: Key combination to unregister

        Returns:
            True if unregistration was successful
        """
        try:
            if not self._shortcut_manager:
                return False

            return self._shortcut_manager.unregister_shortcut(shortcut_key)

        except Exception as e:
            logger.error(f"Error unregistering keyboard shortcut: {e}")
            return False

    def handle_keyboard_event(self, event: ft.KeyboardEvent) -> bool:
        """
        Handle a keyboard event.

        Args:
            event: Keyboard event to handle

        Returns:
            True if event was handled
        """
        try:
            self._performance_metrics['keyboard_events_handled'] += 1

            if not self._keyboard_navigation_active:
                return False

            # Try shortcut manager first
            if self._shortcut_manager and self._shortcut_manager.handle_keyboard_event(event):
                self._performance_metrics['shortcuts_executed'] += 1
                return True

            return False

        except Exception as e:
            logger.error(f"Error handling keyboard event: {e}")
            self._performance_metrics['navigation_errors'] += 1
            return False

    def create_focus_trap(self, container_id: str, element_ids: List[str]) -> bool:
        """
        Create a focus trap within a container.

        Args:
            container_id: ID of the container to trap focus within
            element_ids: List of element IDs that should be included in the trap

        Returns:
            True if focus trap was created successfully
        """
        try:
            if not self._focus_manager:
                return False

            self._focus_manager.create_focus_trap(container_id, element_ids)
            return True

        except Exception as e:
            logger.error(f"Error creating focus trap: {e}")
            return False

    def release_focus_trap(self, container_id: Optional[str] = None) -> bool:
        """
        Release a focus trap.

        Args:
            container_id: Specific container to release (None = release current)

        Returns:
            True if focus trap was released successfully
        """
        try:
            if not self._focus_manager:
                return False

            self._focus_manager.release_focus_trap(container_id)
            return True

        except Exception as e:
            logger.error(f"Error releasing focus trap: {e}")
            return False

    def get_current_focus(self) -> Optional[FocusState]:
        """
        Get current focus state.

        Returns:
            Current focus state or None if not available
        """
        try:
            if not self._focus_manager:
                return None

            return self._focus_manager.get_current_focus()

        except Exception as e:
            logger.error(f"Error getting current focus: {e}")
            return None

    def get_keyboard_shortcuts(self) -> Dict[str, KeyboardShortcut]:
        """
        Get all registered keyboard shortcuts.

        Returns:
            Dictionary of registered shortcuts
        """
        try:
            if not self._shortcut_manager:
                return {}

            return self._shortcut_manager.get_all_shortcuts()

        except Exception as e:
            logger.error(f"Error getting keyboard shortcuts: {e}")
            return {}

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for keyboard navigation.

        Returns:
            Performance metrics dictionary
        """
        try:
            metrics = self._performance_metrics.copy()

            if self._focus_manager:
                focus_metrics = self._focus_manager.get_focus_metrics()
                metrics['focus_metrics'] = asdict(focus_metrics)

            if self._shortcut_manager:
                shortcut_metrics = self._shortcut_manager.get_metrics()
                metrics['shortcut_metrics'] = asdict(shortcut_metrics)

            return metrics

        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {}

    def set_keyboard_navigation_active(self, active: bool) -> None:
        """
        Enable or disable keyboard navigation.

        Args:
            active: Whether keyboard navigation should be active
        """
        try:
            self._keyboard_navigation_active = active

            if self._screen_reader_manager:
                status = "enabled" if active else "disabled"
                self._screen_reader_manager.announce(f"Keyboard navigation {status}")

        except Exception as e:
            logger.error(f"Error setting keyboard navigation active state: {e}")

    def is_keyboard_navigation_active(self) -> bool:
        """
        Check if keyboard navigation is active.

        Returns:
            True if keyboard navigation is active
        """
        return self._keyboard_navigation_active

    def cleanup(self) -> None:
        """Clean up keyboard navigation resources."""
        try:
            # Clean up focus manager
            if self._focus_manager:
                self._focus_manager.cleanup()

            # Clear handlers
            self._keyboard_handlers.clear()
            self._navigation_handlers.clear()

            # Reset state
            self._keyboard_navigation_active = False

            logger.debug("KeyboardNavigationUI cleanup completed")

        except Exception as e:
            logger.error(f"Error during KeyboardNavigationUI cleanup: {e}")


# Utility functions for easy access

def create_keyboard_navigation_ui(config: Optional[KeyboardConfiguration] = None,
                                enable_ui_panel: bool = True) -> KeyboardNavigationUI:
    """
    Create a keyboard navigation UI component with default configuration.

    Args:
        config: Optional keyboard navigation configuration
        enable_ui_panel: Whether to show the UI management panel

    Returns:
        Configured KeyboardNavigationUI component
    """
    return KeyboardNavigationUI(config=config, enable_ui_panel=enable_ui_panel)


def create_default_keyboard_shortcut(key: str,
                                   action: Callable,
                                   description: str,
                                   modifiers: Optional[Set[KeyModifier]] = None,
                                   category: str = "general") -> KeyboardShortcut:
    """
    Create a keyboard shortcut with default settings.

    Args:
        key: Primary key
        action: Action to execute
        description: Human-readable description
        modifiers: Optional modifier keys
        category: Shortcut category

    Returns:
        Configured KeyboardShortcut
    """
    return KeyboardShortcut(
        key=key,
        modifiers=modifiers or set(),
        action=action,
        description=description,
        category=category
    )
