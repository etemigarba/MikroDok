"""
MikroDok Event Bus Package
Provides comprehensive event-driven communication functionality for decoupled component interaction.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        # Enums
        MessageType,
        EventType,
        MessagePriority,
        EventPriority,
        MessageStatus,
        EventStatus,
        DeliveryMode,
        AggregationStrategy,
        
        # Data Classes
        Message,
        Event,
        EventBatch,
        MessageHandler,
        EventHandler,
        DispatchResult,
        AggregationResult,
        MessageConfig,
        EventConfig,
        DispatcherConfig,
        AggregatorConfig,
        
        # Interfaces
        IMessageDispatcher,
        IEventAggregator,
        IMessageHandler,
        IEventHandler
    )
except ImportError:
    pass

# Import message dispatcher components
try:
    from .message_dispatcher_lg import (
        MessageDispatcher,
        MessageRouter,
        SubscriptionManager,
        DeliveryGuarantee,
        Subscription,
        QueuedMessage
    )
except ImportError:
    pass

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
    # Base interfaces and structures
    'MessageType',
    'EventType',
    'MessagePriority',
    'EventPriority',
    'MessageStatus',
    'EventStatus',
    'DeliveryMode',
    'AggregationStrategy',
    'Message',
    'Event',
    'EventBatch',
    'MessageHandler',
    'EventHandler',
    'DispatchResult',
    'AggregationResult',
    'MessageConfig',
    'EventConfig',
    'DispatcherConfig',
    'AggregatorConfig',
    'IMessageDispatcher',
    'IEventAggregator',
    'IMessageHandler',
    'IEventHandler',
    
    # Message Dispatcher
    'MessageDispatcher',
    'MessageRouter',
    'SubscriptionManager',
    'DeliveryGuarantee',
    'Subscription',
    'QueuedMessage',

    # Event Aggregator
    'EventAggregator',
    'EventBatcher',
    'PriorityManager',
    'DeliveryScheduler',
    'EventSubscription',
    'QueuedEvent',
    'AggregationWindow'
]
