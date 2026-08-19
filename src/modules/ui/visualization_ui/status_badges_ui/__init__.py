"""
Module: status_badges_ui
Description: Status badge UI module for MikroDok application.
            Provides comprehensive status indicator badges for training states, model health,
            system status, document processing states, and notification indicators with
            responsive design and theme integration.
Phase: 2-4
Location: /src/modules/ui/visualization_ui/status_badges_ui/
"""

__all__ = [
    "StatusBadgesUI",
    "StatusBadge",
    "StatusType",
    "StatusState",
    "StatusSize",
    "StatusVariant",
    "BadgeConfig",
    "BadgeMetrics",
    "NotificationBadge",
    "CountBadge",
    "HealthBadge",
    "ProcessingBadge",
    "TrainingBadge",
    "SystemBadge",
    "CustomBadge",
    "BadgeGroup",
    "BadgeContainer"
]

# Import status badge components
try:
    from .status_badges_ui import (
        StatusBadgesUI,
        StatusBadge,
        StatusType,
        StatusState,
        StatusSize,
        StatusVariant,
        BadgeConfig,
        BadgeMetrics,
        NotificationBadge,
        CountBadge,
        HealthBadge,
        ProcessingBadge,
        TrainingBadge,
        SystemBadge,
        CustomBadge,
        BadgeGroup,
        BadgeContainer
    )
except ImportError:
    pass
