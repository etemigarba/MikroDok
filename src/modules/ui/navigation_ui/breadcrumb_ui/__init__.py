"""
Module: breadcrumb_ui
Description: Hierarchical breadcrumb navigation component for MikroDok application.
            Provides contextual navigation for deep application states with responsive design,
            theme integration, and accessibility features. Implements modern UI/UX patterns
            with elegant breadcrumb trails and navigation functionality.
Phase: 1
Location: /src/modules/ui/navigation_ui/breadcrumb_ui/
"""

__all__ = [
    "BreadcrumbUI",
    "BreadcrumbItem",
    "BreadcrumbConfig",
    "BreadcrumbState"
]

# Import breadcrumb components when available
try:
    from .breadcrumb_ui import (
        BreadcrumbUI,
        BreadcrumbItem,
        BreadcrumbConfig,
        BreadcrumbState
    )
except ImportError:
    BreadcrumbUI = None
    BreadcrumbItem = None
    BreadcrumbConfig = None
    BreadcrumbState = None
