"""
MikroDok Keyboard Navigation UI Package
Provides comprehensive keyboard navigation interface components including focus management, keyboard shortcuts, and accessibility features.
Phase: 1
Location: /src/modules/ui/accessibility_ui/keyboard_nav_ui/
"""

# Import keyboard navigation components
try:
    from .keyboard_nav_ui import (
        KeyboardNavigationUI,
        KeyboardShortcut,
        FocusManager,
        NavigationMode,
        KeyboardConfiguration,
        ShortcutConflictError
    )
except ImportError:
    pass

__all__ = [
    'KeyboardNavigationUI',
    'KeyboardShortcut', 
    'FocusManager',
    'NavigationMode',
    'KeyboardConfiguration',
    'ShortcutConflictError'
]
