"""
MikroDok Notification UI Package
Provides comprehensive notification components including toast notifications, inline messages, alert banners, and status indicators.
"""

# Import notification components
try:
    from .notification_ui import (
        NotificationUI,
        NotificationItem,
        NotificationConfig,
        NotificationState,
        NotificationType,
        NotificationSeverity,
        NotificationPosition,
        NotificationBehavior,
        ToastNotification,
        InlineNotification,
        BannerNotification,
        StatusNotification,
        NotificationManager,
        NotificationQueue,
        NotificationEvent,
        NotificationCallback,
        create_toast_notification,
        create_inline_notification,
        create_banner_notification,
        create_status_notification
    )
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Notification UI components for MikroDok application"

# Export main components
__all__ = [
    "NotificationUI",
    "NotificationItem",
    "NotificationConfig",
    "NotificationState",
    "NotificationType",
    "NotificationSeverity",
    "NotificationPosition",
    "NotificationBehavior",
    "ToastNotification",
    "InlineNotification",
    "BannerNotification",
    "StatusNotification",
    "NotificationManager",
    "NotificationQueue",
    "NotificationEvent",
    "NotificationCallback",
    "create_toast_notification",
    "create_inline_notification",
    "create_banner_notification",
    "create_status_notification"
]
