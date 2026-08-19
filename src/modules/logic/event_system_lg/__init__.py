"""
MikroDok Event System Package
Provides comprehensive event-driven communication functionality for decoupled component interaction.
"""

# Import base interfaces and common structures
try:
    from src.modules.logic.event_bus_lg.base_interfaces import (
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

# Import event bus components
try:
    from .event_bus_lg.event_bus_lg import (
        EventBus,
        EventBusConfig,
        EventBusMetrics,
        EventBusResult
    )
except ImportError:
    pass

# Import event dispatcher components
try:
    from .event_dispatcher_lg.event_dispatcher_lg import (
        EventDispatcher,
        EventRouter,
        EventSubscriptionManager,
        EventDeliveryGuarantee,
        EventSubscription,
        QueuedEvent
    )
except ImportError:
    pass

# Import event aggregator components
try:
    from .event_aggregator_lg.event_aggregator_lg import (
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

# Import state synchronizer components
try:
    from .state_synchronizer_lg.state_synchronizer_lg import (
        StateSynchronizer,
        StateChangeDetector,
        StateUpdatePropagator,
        ConflictResolver,
        StateUpdate,
        SynchronizationResult
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
    
    # Event Bus
    'EventBus',
    'EventBusConfig',
    'EventBusMetrics',
    'EventBusResult',
    
    # Event Dispatcher
    'EventDispatcher',
    'EventRouter',
    'EventSubscriptionManager',
    'EventDeliveryGuarantee',
    'EventSubscription',
    'QueuedEvent',
    
    # Event Aggregator
    'EventAggregator',
    'EventBatcher',
    'PriorityManager',
    'DeliveryScheduler',
    'EventSubscription',
    'QueuedEvent',
    'AggregationWindow',
    
    # State Synchronizer
    'StateSynchronizer',
    'StateChangeDetector',
    'StateUpdatePropagator',
    'ConflictResolver',
    'StateUpdate',
    'SynchronizationResult'
]
