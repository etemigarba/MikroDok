"""
MikroDok Screen Reader UI Package
Provides comprehensive screen reader support including ARIA labels, live regions, and screen reader optimizations.
Phase: 1
Location: /src/modules/ui/accessibility_ui/screen_reader_ui/
"""

# Import screen reader components
try:
    from .screen_reader_ui import (
        ScreenReaderUI,
        ARIALiveRegion,
        ScreenReaderAnnouncement,
        AccessibilityConfiguration,
        LiveRegionPoliteness,
        ARIARole,
        ARIAProperty,
        ScreenReaderManager,
        AccessibilityState
    )
except ImportError:
    pass

__all__ = [
    'ScreenReaderUI',
    'ARIALiveRegion',
    'ScreenReaderAnnouncement', 
    'AccessibilityConfiguration',
    'LiveRegionPoliteness',
    'ARIARole',
    'ARIAProperty',
    'ScreenReaderManager',
    'AccessibilityState'
]
