"""
MikroDok Toast Manager UI Package
Provides comprehensive toast notification management with stacking, positioning, animations, and theme integration.
"""

# Import toast manager components
try:
    from .toast_manager_ui import (
        ToastManagerUI,
        ToastContainer,
        ToastStack,
        ToastPosition,
        ToastAnimation,
        ToastConfig,
        ToastNotificationItem,
        ToastState,
        ToastBehavior,
        ToastStackManager,
        ToastAnimationController,
        ToastPositionManager,
        create_toast_manager,
        show_toast_notification,
        hide_toast_notification,
        clear_all_toasts,
        get_toast_manager
    )
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Toast notification manager UI component for MikroDok application"

# Export main components
__all__ = [
    "ToastManagerUI",
    "ToastContainer",
    "ToastStack",
    "ToastPosition",
    "ToastAnimation",
    "ToastConfig",
    "ToastNotificationItem",
    "ToastState",
    "ToastBehavior",
    "ToastStackManager",
    "ToastAnimationController",
    "ToastPositionManager",
    "create_toast_manager",
    "show_toast_notification",
    "hide_toast_notification",
    "clear_all_toasts",
    "get_toast_manager"
]
