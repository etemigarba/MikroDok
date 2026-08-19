"""
MikroDok Notification System UI Package
Provides specialized notification system components including toast manager, alert dialogs, progress overlays, and status bar notifications.
"""

# Import notification system components
try:
    from .toast_manager_ui import (
        ToastManagerUI,
        ToastContainer,
        ToastStack,
        ToastPosition,
        ToastAnimation,
        ToastConfig,
        ToastNotificationItem,
        create_toast_manager,
        show_toast_notification
    )
except ImportError:
    pass

try:
    from .alert_dialog_ui import (
        AlertDialogUI,
        AlertType,
        AlertSeverity,
        AlertConfig,
        AlertResult,
        AlertAction,
        create_alert_dialog,
        show_alert_dialog,
        show_confirmation_alert,
        show_warning_alert,
        show_error_alert,
        show_info_alert
    )
except ImportError:
    pass

try:
    from .progress_overlay_ui.progress_overlay_ui import (
        ProgressOverlayUI,
        ProgressConfig,
        ProgressType,
        ProgressState,
        OverlayPosition,
        OverlayAnimation,
        ProgressBehavior,
        ProgressContext,
        ProgressResult,
        create_progress_overlay,
        show_progress_overlay,
        create_fullscreen_progress_overlay,
        create_modal_progress_overlay,
        create_stepped_progress_overlay,
        create_indeterminate_progress_overlay
    )
except ImportError:
    pass

try:
    from .status_bar_ui.status_bar_ui import (
        StatusBarUI,
        StatusConfig,
        StatusType,
        StatusLevel,
        StatusState,
        StatusMessage,
        create_status_bar,
        update_status_bar
    )
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Notification system UI components for MikroDok application"

# Export main components
__all__ = [
    # Toast Manager
    "ToastManagerUI",
    "ToastContainer",
    "ToastStack",
    "ToastPosition",
    "ToastAnimation",
    "ToastConfig",
    "ToastNotificationItem",
    "create_toast_manager",
    "show_toast_notification",
    
    # Alert Dialog
    "AlertDialogUI",
    "AlertType",
    "AlertSeverity",
    "AlertConfig",
    "AlertResult",
    "AlertAction",
    "create_alert_dialog",
    "show_alert_dialog",
    "show_confirmation_alert",
    "show_warning_alert",
    "show_error_alert",
    "show_info_alert",
    
    # Progress Overlay
    "ProgressOverlayUI",
    "ProgressConfig",
    "ProgressType",
    "ProgressState",
    "OverlayPosition",
    "OverlayAnimation",
    "ProgressBehavior",
    "ProgressContext",
    "ProgressResult",
    "create_progress_overlay",
    "show_progress_overlay",
    "create_fullscreen_progress_overlay",
    "create_modal_progress_overlay",
    "create_stepped_progress_overlay",
    "create_indeterminate_progress_overlay",
    
    # Status Bar
    "StatusBarUI",
    "StatusConfig",
    "StatusType",
    "StatusLevel",
    "StatusState",
    "StatusMessage",
    "create_status_bar",
    "update_status_bar"
]
