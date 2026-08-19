"""
Module: navigation_ui
Description: Navigation UI module for MikroDok application.
            Provides comprehensive navigation components including app header, sidebar menu,
            breadcrumb navigation, and footer status bar with responsive design and theme integration.
Phase: 1
Location: /src/modules/ui/navigation_ui/
"""

__all__ = [
    "AppHeaderUI",
    "SidebarMenuUI",
    "SidebarConfig",
    "UserProfile",
    "ResourceStats",
    "QuickLink",
    "NavigationItem",
    "SidebarState",
    "BreadcrumbUI",
    "BreadcrumbItem",
    "BreadcrumbConfig",
    "BreadcrumbState",
    "AccessibleBreadcrumbUI",
    "FooterStatusUI",
    "SystemStatusInfo",
    "ResourceMetrics",
    "FooterConfig",
    "StatusIndicator",
    "QuickAction",
    "StatusLevel",
    "ResourceType"
]

# Import navigation components when available
try:
    from .app_header_ui.app_header_ui import AppHeaderUI
except ImportError:
    AppHeaderUI = None

try:
    from .sidebar_menu_ui.sidebar_menu_ui import (
        SidebarMenuUI,
        SidebarConfig,
        UserProfile,
        ResourceStats,
        QuickLink,
        NavigationItem,
        SidebarState
    )
except ImportError:
    SidebarMenuUI = None
    SidebarConfig = None
    UserProfile = None
    ResourceStats = None
    QuickLink = None
    NavigationItem = None
    SidebarState = None

try:
    from .breadcrumb_ui.breadcrumb_ui import (
        BreadcrumbUI,
        BreadcrumbItem,
        BreadcrumbConfig,
        BreadcrumbState,
        AccessibleBreadcrumbUI
    )
except ImportError:
    BreadcrumbUI = None
    BreadcrumbItem = None
    BreadcrumbConfig = None
    BreadcrumbState = None
    AccessibleBreadcrumbUI = None

try:
    from .footer_status_ui.footer_status_ui import (
        FooterStatusUI,
        SystemStatusInfo,
        ResourceMetrics,
        FooterConfig,
        StatusIndicator,
        QuickAction,
        StatusLevel,
        ResourceType
    )
except ImportError:
    FooterStatusUI = None
    SystemStatusInfo = None
    ResourceMetrics = None
    FooterConfig = None
    StatusIndicator = None
    QuickAction = None
    StatusLevel = None
    ResourceType = None
