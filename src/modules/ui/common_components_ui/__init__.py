"""
MikroDok Common Components UI Package
Provides reusable UI components for the MikroDok application.
"""

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Common UI components for MikroDok application"

# Import form controls components
try:
    from .form_controls_ui import (
        FormControlsUI,
        FormFieldType,
        ValidationRule,
        FormValidationState,
        ButtonVariant,
        InputVariant,
        SelectionVariant
    )
except ImportError:
    pass

# Import table components
try:
    from .table_components_ui import (
        TableComponentsUI,
        DataTableComponent,
        TableColumn,
        TableRow,
        TableCell,
        TablePagination,
        TableFilter,
        TableSort,
        TableConfig,
        TableData,
        SortDirection,
        FilterType,
        ColumnType,
        TableViewMode,
        SelectionMode,
        PaginationConfig,
        FilterConfig,
        SortConfig,
        TableTheme,
        TableState,
        TableEvent,
        TableEventType
    )
except ImportError:
    pass

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

# Export main components
__all__ = [
    # Form controls
    "FormControlsUI",
    "FormFieldType",
    "ValidationRule",
    "FormValidationState",
    "ButtonVariant",
    "InputVariant",
    "SelectionVariant",

    # Table components
    "TableComponentsUI",
    "DataTableComponent",
    "TableColumn",
    "TableRow",
    "TableCell",
    "TablePagination",
    "TableFilter",
    "TableSort",
    "TableConfig",
    "TableData",
    "SortDirection",
    "FilterType",
    "ColumnType",
    "TableViewMode",
    "SelectionMode",
    "PaginationConfig",
    "FilterConfig",
    "SortConfig",
    "TableTheme",
    "TableState",
    "TableEvent",
    "TableEventType",

    # Notification components
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
