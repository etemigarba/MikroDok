"""
Module: base_interfaces
Description: Base interfaces and data structures for event bus system
Phase: 4
Location: /src/modules/logic/event_bus_lg/base_interfaces.py
"""

# Standard library imports
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Union, Set


class MessageType(Enum):
    """Types of messages in the event bus."""
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    NOTIFICATION = "notification"
    COMMAND = "command"
    QUERY = "query"


class EventType(Enum):
    """Types of events in the system."""
    TRAINING_START = "training_start"
    TRAINING_PROGRESS = "training_progress"
    TRAINING_COMPLETE = "training_complete"
    TRAINING_ERROR = "training_error"
    DOCUMENT_PROCESSED = "document_processed"
    INDEXING_COMPLETE = "indexing_complete"
    QUERY_EXECUTED = "query_executed"
    RESOURCE_ALLOCATION = "resource_allocation"
    MEMORY_WARNING = "memory_warning"
    SYSTEM_ERROR = "system_error"
    UI_UPDATE = "ui_update"
    STATE_CHANGE = "state_change"


class MessagePriority(Enum):
    """Priority levels for messages."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


class EventPriority(Enum):
    """Priority levels for events."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


class MessageStatus(Enum):
    """Status of message processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class EventStatus(Enum):
    """Status of event processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    AGGREGATED = "aggregated"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXPIRED = "expired"


class DeliveryMode(Enum):
    """Message delivery modes."""
    FIRE_AND_FORGET = "fire_and_forget"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"
    BEST_EFFORT = "best_effort"


class AggregationStrategy(Enum):
    """Event aggregation strategies."""
    TIME_WINDOW = "time_window"
    COUNT_BASED = "count_based"
    SIZE_BASED = "size_based"
    PRIORITY_BASED = "priority_based"
    ADAPTIVE = "adaptive"


@dataclass
class Message:
    """Data structure representing a message in the event bus."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_type: MessageType = MessageType.EVENT
    action: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    source: Optional[str] = None
    target: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: MessageStatus = MessageStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: Optional[float] = None
    delivery_mode: DeliveryMode = DeliveryMode.BEST_EFFORT


@dataclass
class Event:
    """Data structure representing an event in the system."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.STATE_CHANGE
    source: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: EventStatus = EventStatus.PENDING
    ttl_seconds: Optional[float] = None
    aggregation_key: Optional[str] = None


@dataclass
class EventBatch:
    """Data structure representing a batch of events."""
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    events: List[Event] = field(default_factory=list)
    batch_size: int = 0
    created_timestamp: datetime = field(default_factory=datetime.now)
    aggregation_strategy: AggregationStrategy = AggregationStrategy.TIME_WINDOW
    priority: EventPriority = EventPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        self.batch_size = len(self.events)


@dataclass
class MessageHandler:
    """Data structure representing a message handler."""
    handler_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    handler_func: Optional[Callable] = None
    message_types: Set[MessageType] = field(default_factory=set)
    actions: Set[str] = field(default_factory=set)
    priority: int = 0
    is_async: bool = False
    timeout_seconds: Optional[float] = None
    max_concurrent: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EventHandler:
    """Data structure representing an event handler."""
    handler_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    handler_func: Optional[Callable] = None
    event_types: Set[EventType] = field(default_factory=set)
    sources: Set[str] = field(default_factory=set)
    priority: int = 0
    is_async: bool = False
    timeout_seconds: Optional[float] = None
    max_concurrent: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DispatchResult:
    """Result of message dispatch operation."""
    message_id: str
    success: bool
    delivered_count: int = 0
    failed_count: int = 0
    handlers_called: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregationResult:
    """Result of event aggregation operation."""
    batch_id: str
    success: bool
    events_aggregated: int = 0
    events_delivered: int = 0
    events_failed: int = 0
    batches_created: int = 0
    processing_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MessageConfig:
    """Configuration for message handling."""
    max_retries: int = 3
    timeout_seconds: float = 30.0
    delivery_mode: DeliveryMode = DeliveryMode.BEST_EFFORT
    enable_dead_letter: bool = True
    dead_letter_queue_size: int = 1000
    enable_metrics: bool = True
    enable_tracing: bool = False


@dataclass
class EventConfig:
    """Configuration for event handling."""
    default_ttl_seconds: float = 300.0
    enable_aggregation: bool = True
    aggregation_strategy: AggregationStrategy = AggregationStrategy.TIME_WINDOW
    batch_size_limit: int = 100
    time_window_ms: int = 1000
    enable_metrics: bool = True
    enable_tracing: bool = False


@dataclass
class DispatcherConfig:
    """Configuration for message dispatcher."""
    max_concurrent_dispatches: int = 100
    queue_size_limit: int = 10000
    enable_priority_queue: bool = True
    handler_timeout_seconds: float = 30.0
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = 5
    enable_rate_limiting: bool = False
    rate_limit_per_second: int = 1000


@dataclass
class AggregatorConfig:
    """Configuration for event aggregator."""
    max_batch_size: int = 100
    time_window_ms: int = 1000
    max_concurrent_batches: int = 10
    queue_size_limit: int = 10000
    enable_priority_aggregation: bool = True
    aggregation_timeout_seconds: float = 60.0
    enable_adaptive_batching: bool = True
    min_batch_size: int = 1


class IMessageHandler(ABC):
    """Base interface for message handlers."""
    
    @abstractmethod
    async def handle_message(self, message: Message) -> bool:
        """
        Handle a message.
        
        Args:
            message: Message to handle
            
        Returns:
            True if handled successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def can_handle(self, message: Message) -> bool:
        """
        Check if this handler can handle the message.
        
        Args:
            message: Message to check
            
        Returns:
            True if can handle, False otherwise
        """
        pass


class IEventHandler(ABC):
    """Base interface for event handlers."""
    
    @abstractmethod
    async def handle_event(self, event: Event) -> bool:
        """
        Handle an event.
        
        Args:
            event: Event to handle
            
        Returns:
            True if handled successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def can_handle(self, event: Event) -> bool:
        """
        Check if this handler can handle the event.
        
        Args:
            event: Event to check
            
        Returns:
            True if can handle, False otherwise
        """
        pass


class IMessageDispatcher(ABC):
    """Base interface for message dispatchers."""
    
    @abstractmethod
    async def dispatch_message(self, message: Message) -> DispatchResult:
        """
        Dispatch a message to registered handlers.
        
        Args:
            message: Message to dispatch
            
        Returns:
            DispatchResult with dispatch details
        """
        pass
    
    @abstractmethod
    def subscribe(self, handler: IMessageHandler, 
                 message_types: Optional[Set[MessageType]] = None,
                 actions: Optional[Set[str]] = None) -> str:
        """
        Subscribe a handler to messages.
        
        Args:
            handler: Message handler
            message_types: Optional message types to filter
            actions: Optional actions to filter
            
        Returns:
            Subscription ID
        """
        pass
    
    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe a handler.
        
        Args:
            subscription_id: Subscription identifier
            
        Returns:
            True if unsubscribed successfully
        """
        pass


class IEventAggregator(ABC):
    """Base interface for event aggregators."""
    
    @abstractmethod
    async def aggregate_event(self, event: Event) -> AggregationResult:
        """
        Aggregate an event into batches.
        
        Args:
            event: Event to aggregate
            
        Returns:
            AggregationResult with aggregation details
        """
        pass
    
    @abstractmethod
    def subscribe(self, handler: IEventHandler,
                 event_types: Optional[Set[EventType]] = None,
                 sources: Optional[Set[str]] = None) -> str:
        """
        Subscribe a handler to events.
        
        Args:
            handler: Event handler
            event_types: Optional event types to filter
            sources: Optional sources to filter
            
        Returns:
            Subscription ID
        """
        pass
    
    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe a handler.
        
        Args:
            subscription_id: Subscription identifier
            
        Returns:
            True if unsubscribed successfully
        """
        pass
