"""
MikroDok Event Bus Package
Provides central message bus functionality for decoupled component communication.
"""

# Import event bus components
try:
    from .event_bus_lg import (
        EventBus,
        EventBusConfig,
        EventBusMetrics,
        EventBusResult
    )
except ImportError:
    pass

__all__ = [
    'EventBus',
    'EventBusConfig',
    'EventBusMetrics',
    'EventBusResult'
]
