"""
Module: event_bus_lg
Description: Central message bus for decoupled component communication in MikroDok
Phase: 4
Location: /src/modules/logic/event_system_lg/event_bus_lg/event_bus_lg.py
"""

# Standard library imports
import asyncio
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Set, Optional, Any, Callable, Tuple
from weakref import WeakSet

# Third-party imports
# None required

# Local imports
from src.modules.logic.event_bus_lg.base_interfaces import (
    IMessageDispatcher, IEventAggregator, IMessageHandler, IEventHandler,
    Message, Event, MessageType, EventType, MessagePriority, EventPriority,
    MessageStatus, EventStatus, DeliveryMode, AggregationStrategy,
    DispatchResult, AggregationResult
)
from src.modules.logic.state_management_lg.app_state_manager_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg import ValidationEngine


@dataclass
class EventBusConfig:
    """Configuration for the event bus."""
    max_subscribers: int = 1000
    max_queue_size: int = 10000
    enable_persistence: bool = False
    enable_metrics: bool = True
    enable_dead_letter_queue: bool = True
    message_timeout_seconds: float = 30.0
    event_timeout_seconds: float = 60.0
    cleanup_interval_seconds: float = 300.0
    max_retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    enable_priority_queue: bool = True
    enable_batching: bool = True
    batch_size: int = 100
    batch_timeout_ms: float = 1000.0


@dataclass
class EventBusMetrics:
    """Metrics for event bus operations."""
    messages_published: int = 0
    messages_delivered: int = 0
    messages_failed: int = 0
    events_published: int = 0
    events_delivered: int = 0
    events_failed: int = 0
    subscribers_count: int = 0
    active_subscriptions: int = 0
    queue_size: int = 0
    dead_letter_queue_size: int = 0
    average_delivery_time_ms: float = 0.0
    peak_queue_size: int = 0
    total_processing_time_ms: float = 0.0
    uptime_seconds: float = 0.0


@dataclass
class EventBusResult:
    """Result of event bus operations."""
    success: bool
    operation_id: str = ""
    message: str = ""
    delivery_count: int = 0
    failed_count: int = 0
    processing_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class SubscriptionType(Enum):
    """Types of subscriptions."""
    MESSAGE = "message"
    EVENT = "event"
    BOTH = "both"


@dataclass
class Subscription:
    """Subscription information."""
    subscription_id: str
    subscription_type: SubscriptionType
    handler: Any  # IMessageHandler or IEventHandler
    message_types: Optional[Set[MessageType]] = None
    event_types: Optional[Set[EventType]] = None
    sources: Optional[Set[str]] = None
    actions: Optional[Set[str]] = None
    priority: int = 0
    created_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    delivery_count: int = 0
    failure_count: int = 0
    is_active: bool = True


class EventBus:
    """
    Central event bus for decoupled component communication.
    
    Provides unified message and event routing with subscription management,
    delivery guarantees, and comprehensive monitoring capabilities.
    """
    
    def __init__(self, config: Optional[EventBusConfig] = None):
        """Initialize the event bus."""
        self._config = config or EventBusConfig()
        self._logger = get_log_manager().get_logger(__name__)
        self._validation_engine = ValidationEngine()
        
        # Core state
        self._is_running = False
        self._lock = threading.RLock()
        self._metrics_lock = threading.RLock()
        
        # Subscription management
        self._subscriptions: Dict[str, Subscription] = {}
        self._message_subscriptions: Dict[MessageType, Set[str]] = defaultdict(set)
        self._event_subscriptions: Dict[EventType, Set[str]] = defaultdict(set)
        self._source_subscriptions: Dict[str, Set[str]] = defaultdict(set)
        self._action_subscriptions: Dict[str, Set[str]] = defaultdict(set)
        
        # Message and event queues
        self._message_queue: deque = deque(maxlen=self._config.max_queue_size)
        self._event_queue: deque = deque(maxlen=self._config.max_queue_size)
        self._priority_message_queue: Dict[MessagePriority, deque] = {
            priority: deque() for priority in MessagePriority
        }
        self._priority_event_queue: Dict[EventPriority, deque] = {
            priority: deque() for priority in EventPriority
        }
        
        # Dead letter queues
        self._dead_letter_messages: deque = deque(maxlen=1000)
        self._dead_letter_events: deque = deque(maxlen=1000)
        
        # Metrics and monitoring
        self._metrics = EventBusMetrics()
        self._start_time = datetime.now(timezone.utc)
        
        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Weak references to prevent memory leaks
        self._weak_handlers: WeakSet = WeakSet()
        
        self._logger.info("Event bus initialized")
    
    async def start(self) -> EventBusResult:
        """Start the event bus."""
        start_time = time.time()
        
        try:
            with self._lock:
                if self._is_running:
                    return EventBusResult(
                        success=False,
                        message="Event bus is already running"
                    )
                
                self._is_running = True
                self._start_time = datetime.now(timezone.utc)
                
                # Start background tasks
                if self._config.cleanup_interval_seconds > 0:
                    self._cleanup_task = asyncio.create_task(self._cleanup_loop())
                
                self._logger.info("Event bus started")
                
                return EventBusResult(
                    success=True,
                    message="Event bus started successfully",
                    processing_time_ms=(time.time() - start_time) * 1000
                )
                
        except Exception as e:
            self._logger.error(f"Error starting event bus: {e}")
            return EventBusResult(
                success=False,
                message=f"Failed to start event bus: {e}",
                processing_time_ms=(time.time() - start_time) * 1000
            )
    
    async def stop(self) -> EventBusResult:
        """Stop the event bus."""
        start_time = time.time()
        
        try:
            with self._lock:
                if not self._is_running:
                    return EventBusResult(
                        success=False,
                        message="Event bus is not running"
                    )
                
                self._is_running = False
                
                # Cancel background tasks
                if self._cleanup_task:
                    self._cleanup_task.cancel()
                    try:
                        await self._cleanup_task
                    except asyncio.CancelledError:
                        pass
                
                for task in self._background_tasks:
                    task.cancel()
                
                # Wait for tasks to complete
                if self._background_tasks:
                    await asyncio.gather(*self._background_tasks, return_exceptions=True)
                
                self._background_tasks.clear()
                
                self._logger.info("Event bus stopped")
                
                return EventBusResult(
                    success=True,
                    message="Event bus stopped successfully",
                    processing_time_ms=(time.time() - start_time) * 1000
                )
                
        except Exception as e:
            self._logger.error(f"Error stopping event bus: {e}")
            return EventBusResult(
                success=False,
                message=f"Failed to stop event bus: {e}",
                processing_time_ms=(time.time() - start_time) * 1000
            )

    async def publish_message(self, message: Message) -> EventBusResult:
        """Publish a message to the event bus."""
        start_time = time.time()
        operation_id = str(uuid.uuid4())

        try:
            if not self._is_running:
                return EventBusResult(
                    success=False,
                    operation_id=operation_id,
                    message="Event bus is not running"
                )

            # Validate message
            if not self._validate_message(message):
                return EventBusResult(
                    success=False,
                    operation_id=operation_id,
                    message="Invalid message format"
                )

            # Add to appropriate queue
            if self._config.enable_priority_queue:
                self._priority_message_queue[message.priority].append(message)
            else:
                self._message_queue.append(message)

            # Update metrics
            with self._metrics_lock:
                self._metrics.messages_published += 1
                self._metrics.queue_size = len(self._message_queue)
                if self._metrics.queue_size > self._metrics.peak_queue_size:
                    self._metrics.peak_queue_size = self._metrics.queue_size

            # Process message asynchronously
            task = asyncio.create_task(self._process_message(message))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

            return EventBusResult(
                success=True,
                operation_id=operation_id,
                message="Message published successfully",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            self._logger.error(f"Error publishing message: {e}")
            return EventBusResult(
                success=False,
                operation_id=operation_id,
                message=f"Failed to publish message: {e}",
                processing_time_ms=(time.time() - start_time) * 1000
            )

    async def publish_event(self, event: Event) -> EventBusResult:
        """Publish an event to the event bus."""
        start_time = time.time()
        operation_id = str(uuid.uuid4())

        try:
            if not self._is_running:
                return EventBusResult(
                    success=False,
                    operation_id=operation_id,
                    message="Event bus is not running"
                )

            # Validate event
            if not self._validate_event(event):
                return EventBusResult(
                    success=False,
                    operation_id=operation_id,
                    message="Invalid event format"
                )

            # Add to appropriate queue
            if self._config.enable_priority_queue:
                self._priority_event_queue[event.priority].append(event)
            else:
                self._event_queue.append(event)

            # Update metrics
            with self._metrics_lock:
                self._metrics.events_published += 1
                self._metrics.queue_size = len(self._event_queue)
                if self._metrics.queue_size > self._metrics.peak_queue_size:
                    self._metrics.peak_queue_size = self._metrics.queue_size

            # Process event asynchronously
            task = asyncio.create_task(self._process_event(event))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

            return EventBusResult(
                success=True,
                operation_id=operation_id,
                message="Event published successfully",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            self._logger.error(f"Error publishing event: {e}")
            return EventBusResult(
                success=False,
                operation_id=operation_id,
                message=f"Failed to publish event: {e}",
                processing_time_ms=(time.time() - start_time) * 1000
            )

    def subscribe_to_messages(
        self,
        handler: IMessageHandler,
        message_types: Optional[Set[MessageType]] = None,
        actions: Optional[Set[str]] = None,
        priority: int = 0
    ) -> str:
        """Subscribe a handler to messages."""
        try:
            subscription_id = str(uuid.uuid4())

            subscription = Subscription(
                subscription_id=subscription_id,
                subscription_type=SubscriptionType.MESSAGE,
                handler=handler,
                message_types=message_types,
                actions=actions,
                priority=priority
            )

            with self._lock:
                self._subscriptions[subscription_id] = subscription

                # Index by message types
                if message_types:
                    for msg_type in message_types:
                        self._message_subscriptions[msg_type].add(subscription_id)
                else:
                    # Subscribe to all message types
                    for msg_type in MessageType:
                        self._message_subscriptions[msg_type].add(subscription_id)

                # Index by actions
                if actions:
                    for action in actions:
                        self._action_subscriptions[action].add(subscription_id)

                # Update metrics
                with self._metrics_lock:
                    self._metrics.subscribers_count += 1
                    self._metrics.active_subscriptions += 1

            # Add to weak references
            self._weak_handlers.add(handler)

            self._logger.debug(f"Message subscription created: {subscription_id}")
            return subscription_id

        except Exception as e:
            self._logger.error(f"Error creating message subscription: {e}")
            raise

    def subscribe_to_events(
        self,
        handler: IEventHandler,
        event_types: Optional[Set[EventType]] = None,
        sources: Optional[Set[str]] = None,
        priority: int = 0
    ) -> str:
        """Subscribe a handler to events."""
        try:
            subscription_id = str(uuid.uuid4())

            subscription = Subscription(
                subscription_id=subscription_id,
                subscription_type=SubscriptionType.EVENT,
                handler=handler,
                event_types=event_types,
                sources=sources,
                priority=priority
            )

            with self._lock:
                self._subscriptions[subscription_id] = subscription

                # Index by event types
                if event_types:
                    for event_type in event_types:
                        self._event_subscriptions[event_type].add(subscription_id)
                else:
                    # Subscribe to all event types
                    for event_type in EventType:
                        self._event_subscriptions[event_type].add(subscription_id)

                # Index by sources
                if sources:
                    for source in sources:
                        self._source_subscriptions[source].add(subscription_id)

                # Update metrics
                with self._metrics_lock:
                    self._metrics.subscribers_count += 1
                    self._metrics.active_subscriptions += 1

            # Add to weak references
            self._weak_handlers.add(handler)

            self._logger.debug(f"Event subscription created: {subscription_id}")
            return subscription_id

        except Exception as e:
            self._logger.error(f"Error creating event subscription: {e}")
            raise

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe a handler."""
        try:
            with self._lock:
                if subscription_id not in self._subscriptions:
                    return False

                subscription = self._subscriptions[subscription_id]

                # Remove from indexes
                if subscription.subscription_type in [SubscriptionType.MESSAGE, SubscriptionType.BOTH]:
                    if subscription.message_types:
                        for msg_type in subscription.message_types:
                            self._message_subscriptions[msg_type].discard(subscription_id)
                    else:
                        for msg_type in MessageType:
                            self._message_subscriptions[msg_type].discard(subscription_id)

                    if subscription.actions:
                        for action in subscription.actions:
                            self._action_subscriptions[action].discard(subscription_id)

                if subscription.subscription_type in [SubscriptionType.EVENT, SubscriptionType.BOTH]:
                    if subscription.event_types:
                        for event_type in subscription.event_types:
                            self._event_subscriptions[event_type].discard(subscription_id)
                    else:
                        for event_type in EventType:
                            self._event_subscriptions[event_type].discard(subscription_id)

                    if subscription.sources:
                        for source in subscription.sources:
                            self._source_subscriptions[source].discard(subscription_id)

                # Remove subscription
                del self._subscriptions[subscription_id]

                # Update metrics
                with self._metrics_lock:
                    self._metrics.subscribers_count -= 1
                    self._metrics.active_subscriptions -= 1

            self._logger.debug(f"Subscription removed: {subscription_id}")
            return True

        except Exception as e:
            self._logger.error(f"Error removing subscription: {e}")
            return False

    def get_metrics(self) -> EventBusMetrics:
        """Get current event bus metrics."""
        with self._metrics_lock:
            # Update uptime
            self._metrics.uptime_seconds = (
                datetime.now(timezone.utc) - self._start_time
            ).total_seconds()

            return self._metrics

    def get_subscription_info(self, subscription_id: str) -> Optional[Subscription]:
        """Get subscription information."""
        with self._lock:
            return self._subscriptions.get(subscription_id)

    def list_subscriptions(self) -> List[Subscription]:
        """List all active subscriptions."""
        with self._lock:
            return list(self._subscriptions.values())

    def get_queue_sizes(self) -> Dict[str, int]:
        """Get current queue sizes."""
        return {
            'message_queue': len(self._message_queue),
            'event_queue': len(self._event_queue),
            'dead_letter_messages': len(self._dead_letter_messages),
            'dead_letter_events': len(self._dead_letter_events)
        }

    async def _process_message(self, message: Message) -> None:
        """Process a message by delivering to subscribers."""
        try:
            # Get matching subscriptions
            matching_subscriptions = self._get_matching_message_subscriptions(message)

            if not matching_subscriptions:
                return

            # Sort by priority
            sorted_subscriptions = sorted(
                matching_subscriptions,
                key=lambda s: s.priority,
                reverse=True
            )

            # Deliver to handlers
            delivery_count = 0
            failed_count = 0

            for subscription in sorted_subscriptions:
                try:
                    if subscription.is_active:
                        await subscription.handler.handle_message(message)
                        subscription.delivery_count += 1
                        subscription.last_activity = datetime.now(timezone.utc)
                        delivery_count += 1

                except Exception as e:
                    self._logger.warning(f"Handler failed for message {message.message_id}: {e}")
                    subscription.failure_count += 1
                    failed_count += 1

                    # Deactivate handler after too many failures
                    if subscription.failure_count >= self._config.max_retry_attempts:
                        subscription.is_active = False

            # Update metrics
            with self._metrics_lock:
                self._metrics.messages_delivered += delivery_count
                self._metrics.messages_failed += failed_count

            # Move to dead letter queue if all deliveries failed
            if delivery_count == 0 and len(matching_subscriptions) > 0:
                if self._config.enable_dead_letter_queue:
                    self._dead_letter_messages.append(message)

        except Exception as e:
            self._logger.error(f"Error processing message {message.message_id}: {e}")

    async def _process_event(self, event: Event) -> None:
        """Process an event by delivering to subscribers."""
        try:
            # Get matching subscriptions
            matching_subscriptions = self._get_matching_event_subscriptions(event)

            if not matching_subscriptions:
                return

            # Sort by priority
            sorted_subscriptions = sorted(
                matching_subscriptions,
                key=lambda s: s.priority,
                reverse=True
            )

            # Deliver to handlers
            delivery_count = 0
            failed_count = 0

            for subscription in sorted_subscriptions:
                try:
                    if subscription.is_active:
                        await subscription.handler.handle_event(event)
                        subscription.delivery_count += 1
                        subscription.last_activity = datetime.now(timezone.utc)
                        delivery_count += 1

                except Exception as e:
                    self._logger.warning(f"Handler failed for event {event.event_id}: {e}")
                    subscription.failure_count += 1
                    failed_count += 1

                    # Deactivate handler after too many failures
                    if subscription.failure_count >= self._config.max_retry_attempts:
                        subscription.is_active = False

            # Update metrics
            with self._metrics_lock:
                self._metrics.events_delivered += delivery_count
                self._metrics.events_failed += failed_count

            # Move to dead letter queue if all deliveries failed
            if delivery_count == 0 and len(matching_subscriptions) > 0:
                if self._config.enable_dead_letter_queue:
                    self._dead_letter_events.append(event)

        except Exception as e:
            self._logger.error(f"Error processing event {event.event_id}: {e}")

    def _get_matching_message_subscriptions(self, message: Message) -> List[Subscription]:
        """Get subscriptions that match a message."""
        matching_subscriptions = []

        with self._lock:
            # Get subscriptions by message type
            subscription_ids = self._message_subscriptions.get(message.message_type, set())

            # Get subscriptions by action
            if message.action:
                subscription_ids.update(self._action_subscriptions.get(message.action, set()))

            # Filter and validate subscriptions
            for subscription_id in subscription_ids:
                subscription = self._subscriptions.get(subscription_id)
                if subscription and subscription.is_active:
                    if self._message_matches_subscription(message, subscription):
                        matching_subscriptions.append(subscription)

        return matching_subscriptions

    def _get_matching_event_subscriptions(self, event: Event) -> List[Subscription]:
        """Get subscriptions that match an event."""
        matching_subscriptions = []

        with self._lock:
            # Get subscriptions by event type
            subscription_ids = self._event_subscriptions.get(event.event_type, set())

            # Get subscriptions by source
            if event.source:
                subscription_ids.update(self._source_subscriptions.get(event.source, set()))

            # Filter and validate subscriptions
            for subscription_id in subscription_ids:
                subscription = self._subscriptions.get(subscription_id)
                if subscription and subscription.is_active:
                    if self._event_matches_subscription(event, subscription):
                        matching_subscriptions.append(subscription)

        return matching_subscriptions

    def _message_matches_subscription(self, message: Message, subscription: Subscription) -> bool:
        """Check if a message matches a subscription."""
        # Check message type
        if subscription.message_types and message.message_type not in subscription.message_types:
            return False

        # Check action
        if subscription.actions and message.action not in subscription.actions:
            return False

        return True

    def _event_matches_subscription(self, event: Event, subscription: Subscription) -> bool:
        """Check if an event matches a subscription."""
        # Check event type
        if subscription.event_types and event.event_type not in subscription.event_types:
            return False

        # Check source
        if subscription.sources and event.source not in subscription.sources:
            return False

        return True

    def _validate_message(self, message: Message) -> bool:
        """Validate a message."""
        try:
            return (
                message.message_id and
                isinstance(message.message_type, MessageType) and
                isinstance(message.priority, MessagePriority) and
                isinstance(message.timestamp, datetime)
            )
        except Exception:
            return False

    def _validate_event(self, event: Event) -> bool:
        """Validate an event."""
        try:
            return (
                event.event_id and
                isinstance(event.event_type, EventType) and
                isinstance(event.priority, EventPriority) and
                isinstance(event.timestamp, datetime)
            )
        except Exception:
            return False

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while self._is_running:
            try:
                await asyncio.sleep(self._config.cleanup_interval_seconds)

                if not self._is_running:
                    break

                # Clean up inactive subscriptions
                await self._cleanup_inactive_subscriptions()

                # Clean up expired messages and events
                await self._cleanup_expired_items()

                # Update metrics
                self._update_metrics()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(1.0)

    async def _cleanup_inactive_subscriptions(self) -> None:
        """Clean up inactive subscriptions."""
        try:
            inactive_subscriptions = []
            current_time = datetime.now(timezone.utc)

            with self._lock:
                for subscription_id, subscription in self._subscriptions.items():
                    # Check if handler is still alive (weak reference)
                    if subscription.handler not in self._weak_handlers:
                        inactive_subscriptions.append(subscription_id)
                    # Check for long inactivity
                    elif (current_time - subscription.last_activity).total_seconds() > 3600:  # 1 hour
                        if subscription.failure_count > subscription.delivery_count:
                            inactive_subscriptions.append(subscription_id)

            # Remove inactive subscriptions
            for subscription_id in inactive_subscriptions:
                self.unsubscribe(subscription_id)

        except Exception as e:
            self._logger.error(f"Error cleaning up subscriptions: {e}")

    async def _cleanup_expired_items(self) -> None:
        """Clean up expired messages and events."""
        try:
            current_time = datetime.now(timezone.utc)

            # Clean up message queues
            self._cleanup_queue(self._message_queue, current_time, self._config.message_timeout_seconds)
            for priority_queue in self._priority_message_queue.values():
                self._cleanup_queue(priority_queue, current_time, self._config.message_timeout_seconds)

            # Clean up event queues
            self._cleanup_queue(self._event_queue, current_time, self._config.event_timeout_seconds)
            for priority_queue in self._priority_event_queue.values():
                self._cleanup_queue(priority_queue, current_time, self._config.event_timeout_seconds)

        except Exception as e:
            self._logger.error(f"Error cleaning up expired items: {e}")

    def _cleanup_queue(self, queue: deque, current_time: datetime, timeout_seconds: float) -> None:
        """Clean up expired items from a queue."""
        try:
            items_to_remove = []

            for item in queue:
                if hasattr(item, 'timestamp'):
                    age_seconds = (current_time - item.timestamp).total_seconds()
                    if age_seconds > timeout_seconds:
                        items_to_remove.append(item)

            for item in items_to_remove:
                try:
                    queue.remove(item)
                except ValueError:
                    pass  # Item already removed

        except Exception as e:
            self._logger.error(f"Error cleaning up queue: {e}")

    def _update_metrics(self) -> None:
        """Update metrics."""
        try:
            with self._metrics_lock:
                self._metrics.queue_size = len(self._message_queue) + len(self._event_queue)
                self._metrics.dead_letter_queue_size = (
                    len(self._dead_letter_messages) + len(self._dead_letter_events)
                )
                self._metrics.active_subscriptions = len([
                    s for s in self._subscriptions.values() if s.is_active
                ])

        except Exception as e:
            self._logger.error(f"Error updating metrics: {e}")
