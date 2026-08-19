"""
MikroDok Message Dispatcher Package
Provides message routing and dispatch functionality for publish-subscribe communication.
"""

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

__all__ = [
    'MessageDispatcher',
    'MessageRouter',
    'SubscriptionManager',
    'DeliveryGuarantee',
    'Subscription',
    'QueuedMessage'
]
