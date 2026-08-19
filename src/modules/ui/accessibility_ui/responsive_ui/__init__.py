"""
Module: responsive_ui
Description: Responsive breakpoint handlers and adaptive layouts for accessibility compliance.
            Provides comprehensive responsive design capabilities with WCAG 2.1 AA compliance
            and seamless integration with the MikroDok theme system.

Phase: 1
Location: /src/modules/ui/accessibility_ui/responsive_ui/
"""

from .responsive_ui import (
    ResponsiveUI,
    ResponsiveBreakpointHandler,
    AdaptiveLayoutManager,
    AccessibilityResponsiveManager,
    ResponsiveEventHandler,
    ResponsiveComponentFactory,
    ResponsiveUtilities
)

__all__ = [
    'ResponsiveUI',
    'ResponsiveBreakpointHandler', 
    'AdaptiveLayoutManager',
    'AccessibilityResponsiveManager',
    'ResponsiveEventHandler',
    'ResponsiveComponentFactory',
    'ResponsiveUtilities'
]
