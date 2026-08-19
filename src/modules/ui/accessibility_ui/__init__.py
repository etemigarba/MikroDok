"""
MikroDok Accessibility UI Package
Provides comprehensive accessibility interface components including screen reader support, keyboard navigation, high contrast mode, and responsive accessibility features.
Phase: 1
Location: /src/modules/ui/accessibility_ui/
"""

# Import accessibility components
try:
    from .screen_reader_ui.screen_reader_ui import (
        ScreenReaderUI,
        ARIALiveRegion,
        ScreenReaderAnnouncement,
        AccessibilityConfiguration,
        LiveRegionPoliteness
    )
except ImportError:
    pass

try:
    from .keyboard_nav_ui.keyboard_nav_ui import (
        KeyboardNavigationUI,
        KeyboardShortcut,
        FocusManager,
        NavigationMode
    )
except ImportError:
    pass

try:
    from .high_contrast_ui.high_contrast_ui import (
        HighContrastUI,
        ContrastMode,
        ColorBlindnessSupport,
        AccessibilityTheme
    )
except ImportError:
    pass

try:
    from .responsive_ui.responsive_ui import (
        ResponsiveAccessibilityUI,
        AccessibilityBreakpoints,
        ResponsiveAccessibilityManager
    )
except ImportError:
    pass

__all__ = [
    # Screen Reader Components
    'ScreenReaderUI',
    'ARIALiveRegion', 
    'ScreenReaderAnnouncement',
    'AccessibilityConfiguration',
    'LiveRegionPoliteness',
    
    # Keyboard Navigation Components
    'KeyboardNavigationUI',
    'KeyboardShortcut',
    'FocusManager',
    'NavigationMode',
    
    # High Contrast Components
    'HighContrastUI',
    'ContrastMode',
    'ColorBlindnessSupport',
    'AccessibilityTheme',
    
    # Responsive Accessibility Components
    'ResponsiveAccessibilityUI',
    'AccessibilityBreakpoints',
    'ResponsiveAccessibilityManager'
]
