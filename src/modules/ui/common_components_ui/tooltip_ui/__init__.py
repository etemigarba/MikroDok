"""
Module: tooltip_ui
Description: Context-sensitive tooltips and help popovers for MikroDok application
Phase: 1
Location: /src/modules/ui/common_components_ui/tooltip_ui/

This module provides comprehensive tooltip functionality including:
- Context-sensitive tooltips with intelligent positioning
- Rich content support (text, icons, images, interactive elements)
- Responsive design with breakpoint-aware sizing
- Accessibility compliance (WCAG 2.1 AA)
- Theme system integration
- Performance optimization with pooling and caching
- Global tooltip management and coordination
"""

from .tooltip_ui import (
    TooltipUI,
    TooltipPosition,
    TooltipTrigger,
    TooltipConfig,
    TooltipContent,
    TooltipManager,
    TooltipVariant,
    TooltipState
)

__all__ = [
    'TooltipUI',
    'TooltipPosition',
    'TooltipTrigger', 
    'TooltipConfig',
    'TooltipContent',
    'TooltipManager',
    'TooltipVariant',
    'TooltipState'
]
