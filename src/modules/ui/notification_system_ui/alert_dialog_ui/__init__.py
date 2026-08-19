"""
Alert Dialog UI Module

This module provides alert dialog components for the notification system UI.
Shows modal alerts for critical messages with comprehensive configuration options.

Phase: 1
Location: /src/modules/ui/notification_system_ui/alert_dialog_ui/
"""

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

__all__ = [
    'AlertDialogUI',
    'AlertType',
    'AlertSeverity', 
    'AlertConfig',
    'AlertResult',
    'AlertAction',
    'create_alert_dialog',
    'show_alert_dialog',
    'show_confirmation_alert',
    'show_warning_alert',
    'show_error_alert',
    'show_info_alert'
]
