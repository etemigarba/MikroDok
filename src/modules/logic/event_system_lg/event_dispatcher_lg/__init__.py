"""
MikroDok Event Dispatcher Package
Provides event routing and dispatch functionality with filtering and priority management.
"""

# Import event dispatcher components
try:
    from .event_dispatcher_lg import (
        EventDispatcher,
        EventRouter,
        EventSubscriptionManager,
        EventDeliveryGuarantee,
        EventSubscription,
        QueuedEvent
    )
except ImportError:
    pass

__all__ = [
    'EventDispatcher',
    'EventRouter',
    'EventSubscriptionManager',
    'EventDeliveryGuarantee',
    'EventSubscription',
    'QueuedEvent'
]
