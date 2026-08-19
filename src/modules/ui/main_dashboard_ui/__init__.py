"""
Main Dashboard UI Module

This module contains the main dashboard interface components for MikroDok application.
Provides the central landing page, project management cards, quick actions, and activity feed.

Phase: 1
Location: /src/modules/ui/main_dashboard_ui/
"""

from .landing_page_ui.landing_page_ui import LandingPageUI
from .project_cards_ui.project_cards_ui import (
    ProjectCardsUI,
    ProjectCardData,
    ProjectCardConfig,
    ProjectCardLayout,
    ProjectStatus,
    ProjectType,
    SortOption
)
from .quick_actions_ui.quick_actions_ui import (
    QuickActionsUI,
    QuickAction,
    QuickActionsConfig,
    ActionLayout,
    ActionSize,
    ActionStyle,
    create_default_actions
)
from .activity_feed_ui.activity_feed_ui import (
    ActivityFeedUI,
    ActivityItem,
    ActivityFeedConfig,
    ActivityFilter,
    ActivityCategory,
    ActivityStatus,
    ActivityPriority,
    ActivitySource
)

__all__ = [
    'LandingPageUI',
    'ProjectCardsUI',
    'ProjectCardData',
    'ProjectCardConfig',
    'ProjectCardLayout',
    'ProjectStatus',
    'ProjectType',
    'SortOption',
    'QuickActionsUI',
    'QuickAction',
    'QuickActionsConfig',
    'ActionLayout',
    'ActionSize',
    'ActionStyle',
    'create_default_actions',
    'ActivityFeedUI',
    'ActivityItem',
    'ActivityFeedConfig',
    'ActivityFilter',
    'ActivityCategory',
    'ActivityStatus',
    'ActivityPriority',
    'ActivitySource'
]
