"""
MikroDok Event Aggregator Package
Provides event batching and aggregation functionality for efficient event processing.
"""

# Import event aggregator components
try:
    from .event_aggregator_lg import (
        EventAggregator,
        EventBatcher,
        PriorityManager,
        DeliveryScheduler,
        EventSubscription,
        QueuedEvent,
        AggregationWindow
    )
except ImportError:
    pass

__all__ = [
    'EventAggregator',
    'EventBatcher',
    'PriorityManager',
    'DeliveryScheduler',
    'EventSubscription',
    'QueuedEvent',
    'AggregationWindow'
]
