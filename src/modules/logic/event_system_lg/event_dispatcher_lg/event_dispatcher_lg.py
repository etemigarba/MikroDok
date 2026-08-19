"""
Module: event_dispatcher_lg
Description: Routes events to appropriate handlers with filtering and priority management
Phase: 4
Location: /src/modules/logic/event_system_lg/event_dispatcher_lg/event_dispatcher_lg.py
"""

# Standard library imports
import asyncio
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Set, Optional, Any, Callable, Tuple
from weakref import WeakSet

# Third-party imports
# None required

# Local imports
from src.modules.logic.event_bus_lg.base_interfaces import (
    IEventHandler, Event, EventType, EventPriority, EventStatus,
    AggregationStrategy, EventBatch, AggregationResult
)
from src.modules.logic.state_management_lg.app_state_manager_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg import ValidationEngine


class FilterType(Enum):
    """Types of event filters."""
    EVENT_TYPE = "event_type"
    SOURCE = "source"
    PRIORITY = "priority"
    TAG = "tag"
    METADATA = "metadata"
    CUSTOM = "custom"


class RoutingStrategy(Enum):
    """Event routing strategies."""
    ROUND_ROBIN = "round_robin"
    PRIORITY_BASED = "priority_based"
    LOAD_BALANCED = "load_balanced"
    BROADCAST = "broadcast"
    FIRST_AVAILABLE = "first_available"


@dataclass
class EventFilter:
    """Event filter configuration."""
    filter_id: str
    filter_type: FilterType
    criteria: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    priority: int = 0
    created_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EventRoute:
    """Event routing configuration."""
    route_id: str
    source_pattern: str = "*"
    event_types: Set[EventType] = field(default_factory=set)
    target_handlers: List[str] = field(default_factory=list)
    filters: List[EventFilter] = field(default_factory=list)
    routing_strategy: RoutingStrategy = RoutingStrategy.BROADCAST
    priority: int = 0
    is_active: bool = True
    created_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    usage_count: int = 0


@dataclass
class EventSubscription:
    """Event subscription information."""
    subscription_id: str
    handler: IEventHandler
    event_types: Set[EventType] = field(default_factory=set)
    sources: Set[str] = field(default_factory=set)
    filters: List[EventFilter] = field(default_factory=list)
    priority: int = 0
    is_active: bool = True
    created_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    delivery_count: int = 0
    failure_count: int = 0
    max_failures: int = 5


@dataclass
class QueuedEvent:
    """Queued event with metadata."""
    event: Event
    subscription_ids: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    queued_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_attempt: Optional[datetime] = None
    next_retry: Optional[datetime] = None


@dataclass
class DispatcherConfig:
    """Configuration for the event dispatcher."""
    max_queue_size: int = 10000
    max_concurrent_dispatches: int = 100
    enable_filtering: bool = True
    enable_routing: bool = True
    enable_priority_queue: bool = True
    enable_retry: bool = True
    max_retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    batch_size: int = 50
    batch_timeout_ms: float = 100.0
    cleanup_interval_seconds: float = 300.0
    metrics_enabled: bool = True


@dataclass
class DispatcherMetrics:
    """Metrics for event dispatcher operations."""
    events_received: int = 0
    events_dispatched: int = 0
    events_filtered: int = 0
    events_failed: int = 0
    events_retried: int = 0
    active_subscriptions: int = 0
    active_routes: int = 0
    queue_size: int = 0
    average_dispatch_time_ms: float = 0.0
    peak_queue_size: int = 0
    total_processing_time_ms: float = 0.0
    uptime_seconds: float = 0.0


@dataclass
class DispatchResult:
    """Result of event dispatch operation."""
    success: bool
    event_id: str = ""
    dispatched_count: int = 0
    failed_count: int = 0
    filtered_count: int = 0
    handlers_called: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class EventRouter:
    """
    Event routing engine for determining event destinations.
    
    Manages routing rules, filters, and strategies for efficient
    event distribution to appropriate handlers.
    """
    
    def __init__(self):
        """Initialize the event router."""
        self._routes: Dict[str, EventRoute] = {}
        self._filters: Dict[str, EventFilter] = {}
        self._lock = threading.RLock()
        self._logger = get_log_manager().get_logger(__name__)
        
        # Routing state
        self._round_robin_counters: Dict[str, int] = defaultdict(int)
        self._handler_loads: Dict[str, int] = defaultdict(int)
    
    def add_route(self, route: EventRoute) -> bool:
        """Add a routing rule."""
        try:
            with self._lock:
                self._routes[route.route_id] = route
                self._logger.debug(f"Route added: {route.route_id}")
                return True
                
        except Exception as e:
            self._logger.error(f"Error adding route: {e}")
            return False
    
    def remove_route(self, route_id: str) -> bool:
        """Remove a routing rule."""
        try:
            with self._lock:
                if route_id in self._routes:
                    del self._routes[route_id]
                    self._logger.debug(f"Route removed: {route_id}")
                    return True
                return False
                
        except Exception as e:
            self._logger.error(f"Error removing route: {e}")
            return False
    
    def add_filter(self, filter_config: EventFilter) -> bool:
        """Add an event filter."""
        try:
            with self._lock:
                self._filters[filter_config.filter_id] = filter_config
                self._logger.debug(f"Filter added: {filter_config.filter_id}")
                return True
                
        except Exception as e:
            self._logger.error(f"Error adding filter: {e}")
            return False
    
    def remove_filter(self, filter_id: str) -> bool:
        """Remove an event filter."""
        try:
            with self._lock:
                if filter_id in self._filters:
                    del self._filters[filter_id]
                    self._logger.debug(f"Filter removed: {filter_id}")
                    return True
                return False
                
        except Exception as e:
            self._logger.error(f"Error removing filter: {e}")
            return False
    
    def route_event(self, event: Event, available_handlers: List[str]) -> List[str]:
        """Route an event to appropriate handlers."""
        try:
            with self._lock:
                # Find matching routes
                matching_routes = self._find_matching_routes(event)
                
                if not matching_routes:
                    return available_handlers  # Default to all handlers
                
                # Apply routing strategies
                selected_handlers = []
                for route in matching_routes:
                    if route.is_active:
                        route_handlers = self._apply_routing_strategy(
                            route, available_handlers
                        )
                        selected_handlers.extend(route_handlers)
                        
                        # Update route usage
                        route.usage_count += 1
                        route.last_used = datetime.now(timezone.utc)
                
                return list(set(selected_handlers))  # Remove duplicates
                
        except Exception as e:
            self._logger.error(f"Error routing event: {e}")
            return available_handlers

    def _find_matching_routes(self, event: Event) -> List[EventRoute]:
        """Find routes that match an event."""
        matching_routes = []

        for route in self._routes.values():
            if self._route_matches_event(route, event):
                matching_routes.append(route)

        # Sort by priority
        return sorted(matching_routes, key=lambda r: r.priority, reverse=True)

    def _route_matches_event(self, route: EventRoute, event: Event) -> bool:
        """Check if a route matches an event."""
        # Check event types
        if route.event_types and event.event_type not in route.event_types:
            return False

        # Check source pattern
        if route.source_pattern != "*":
            if not self._matches_pattern(event.source, route.source_pattern):
                return False

        # Apply filters
        for filter_config in route.filters:
            if filter_config.is_active:
                if not self._apply_filter(event, filter_config):
                    return False

        return True

    def _matches_pattern(self, source: str, pattern: str) -> bool:
        """Check if source matches pattern (simple wildcard support)."""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return source.startswith(pattern[:-1])
        if pattern.startswith("*"):
            return source.endswith(pattern[1:])
        return source == pattern

    def _apply_filter(self, event: Event, filter_config: EventFilter) -> bool:
        """Apply a filter to an event."""
        try:
            if filter_config.filter_type == FilterType.EVENT_TYPE:
                allowed_types = filter_config.criteria.get("types", [])
                return event.event_type in allowed_types

            elif filter_config.filter_type == FilterType.SOURCE:
                allowed_sources = filter_config.criteria.get("sources", [])
                return event.source in allowed_sources

            elif filter_config.filter_type == FilterType.PRIORITY:
                min_priority = filter_config.criteria.get("min_priority", EventPriority.LOW)
                return event.priority.value >= min_priority.value

            elif filter_config.filter_type == FilterType.TAG:
                required_tags = set(filter_config.criteria.get("tags", []))
                return required_tags.issubset(event.tags)

            elif filter_config.filter_type == FilterType.METADATA:
                required_metadata = filter_config.criteria.get("metadata", {})
                for key, value in required_metadata.items():
                    if event.metadata.get(key) != value:
                        return False
                return True

            elif filter_config.filter_type == FilterType.CUSTOM:
                # Custom filter function
                filter_func = filter_config.criteria.get("function")
                if callable(filter_func):
                    return filter_func(event)

            return True

        except Exception as e:
            self._logger.error(f"Error applying filter {filter_config.filter_id}: {e}")
            return True  # Default to allowing event

    def _apply_routing_strategy(self, route: EventRoute, available_handlers: List[str]) -> List[str]:
        """Apply routing strategy to select handlers."""
        try:
            # Filter handlers based on route targets
            target_handlers = []
            if route.target_handlers:
                target_handlers = [h for h in available_handlers if h in route.target_handlers]
            else:
                target_handlers = available_handlers

            if not target_handlers:
                return []

            if route.routing_strategy == RoutingStrategy.BROADCAST:
                return target_handlers

            elif route.routing_strategy == RoutingStrategy.ROUND_ROBIN:
                counter = self._round_robin_counters[route.route_id]
                selected = target_handlers[counter % len(target_handlers)]
                self._round_robin_counters[route.route_id] = counter + 1
                return [selected]

            elif route.routing_strategy == RoutingStrategy.PRIORITY_BASED:
                # Sort by priority (assuming handlers have priority metadata)
                return sorted(target_handlers, key=lambda h: self._get_handler_priority(h), reverse=True)[:1]

            elif route.routing_strategy == RoutingStrategy.LOAD_BALANCED:
                # Select handler with lowest load
                min_load_handler = min(target_handlers, key=lambda h: self._handler_loads[h])
                return [min_load_handler]

            elif route.routing_strategy == RoutingStrategy.FIRST_AVAILABLE:
                return target_handlers[:1]

            return target_handlers

        except Exception as e:
            self._logger.error(f"Error applying routing strategy: {e}")
            return available_handlers

    def _get_handler_priority(self, handler_id: str) -> int:
        """Get handler priority (placeholder implementation)."""
        return 0  # Default priority

    def update_handler_load(self, handler_id: str, load_delta: int) -> None:
        """Update handler load for load balancing."""
        with self._lock:
            self._handler_loads[handler_id] += load_delta
            if self._handler_loads[handler_id] < 0:
                self._handler_loads[handler_id] = 0


class EventSubscriptionManager:
    """
    Manages event subscriptions and handler registration.

    Provides subscription lifecycle management, filtering,
    and efficient lookup for event routing.
    """

    def __init__(self):
        """Initialize the subscription manager."""
        self._subscriptions: Dict[str, EventSubscription] = {}
        self._event_type_index: Dict[EventType, Set[str]] = defaultdict(set)
        self._source_index: Dict[str, Set[str]] = defaultdict(set)
        self._lock = threading.RLock()
        self._logger = get_log_manager().get_logger(__name__)

        # Weak references to prevent memory leaks
        self._weak_handlers: WeakSet = WeakSet()

    def add_subscription(
        self,
        handler: IEventHandler,
        event_types: Optional[Set[EventType]] = None,
        sources: Optional[Set[str]] = None,
        filters: Optional[List[EventFilter]] = None,
        priority: int = 0
    ) -> str:
        """Add an event subscription."""
        try:
            subscription_id = str(uuid.uuid4())

            subscription = EventSubscription(
                subscription_id=subscription_id,
                handler=handler,
                event_types=event_types or set(),
                sources=sources or set(),
                filters=filters or [],
                priority=priority
            )

            with self._lock:
                self._subscriptions[subscription_id] = subscription

                # Index by event types
                if event_types:
                    for event_type in event_types:
                        self._event_type_index[event_type].add(subscription_id)
                else:
                    # Subscribe to all event types
                    for event_type in EventType:
                        self._event_type_index[event_type].add(subscription_id)

                # Index by sources
                if sources:
                    for source in sources:
                        self._source_index[source].add(subscription_id)

            # Add to weak references
            self._weak_handlers.add(handler)

            self._logger.debug(f"Subscription added: {subscription_id}")
            return subscription_id

        except Exception as e:
            self._logger.error(f"Error adding subscription: {e}")
            raise

    def remove_subscription(self, subscription_id: str) -> bool:
        """Remove an event subscription."""
        try:
            with self._lock:
                if subscription_id not in self._subscriptions:
                    return False

                subscription = self._subscriptions[subscription_id]

                # Remove from indexes
                if subscription.event_types:
                    for event_type in subscription.event_types:
                        self._event_type_index[event_type].discard(subscription_id)
                else:
                    for event_type in EventType:
                        self._event_type_index[event_type].discard(subscription_id)

                if subscription.sources:
                    for source in subscription.sources:
                        self._source_index[source].discard(subscription_id)

                # Remove subscription
                del self._subscriptions[subscription_id]

            self._logger.debug(f"Subscription removed: {subscription_id}")
            return True

        except Exception as e:
            self._logger.error(f"Error removing subscription: {e}")
            return False

    def get_matching_subscriptions(self, event: Event) -> List[EventSubscription]:
        """Get subscriptions that match an event."""
        matching_subscriptions = []

        with self._lock:
            # Get subscriptions by event type
            subscription_ids = self._event_type_index.get(event.event_type, set()).copy()

            # Get subscriptions by source
            if event.source:
                subscription_ids.update(self._source_index.get(event.source, set()))

            # Filter and validate subscriptions
            for subscription_id in subscription_ids:
                subscription = self._subscriptions.get(subscription_id)
                if subscription and subscription.is_active:
                    if self._event_matches_subscription(event, subscription):
                        matching_subscriptions.append(subscription)

        # Sort by priority
        return sorted(matching_subscriptions, key=lambda s: s.priority, reverse=True)

    def _event_matches_subscription(self, event: Event, subscription: EventSubscription) -> bool:
        """Check if an event matches a subscription."""
        # Check event types
        if subscription.event_types and event.event_type not in subscription.event_types:
            return False

        # Check sources
        if subscription.sources and event.source not in subscription.sources:
            return False

        # Apply filters
        for filter_config in subscription.filters:
            if filter_config.is_active:
                router = EventRouter()  # Temporary instance for filter application
                if not router._apply_filter(event, filter_config):
                    return False

        return True

    def get_subscription(self, subscription_id: str) -> Optional[EventSubscription]:
        """Get subscription by ID."""
        with self._lock:
            return self._subscriptions.get(subscription_id)

    def list_subscriptions(self) -> List[EventSubscription]:
        """List all active subscriptions."""
        with self._lock:
            return [s for s in self._subscriptions.values() if s.is_active]

    def cleanup_inactive_subscriptions(self) -> int:
        """Clean up inactive subscriptions."""
        removed_count = 0
        inactive_subscriptions = []

        with self._lock:
            for subscription_id, subscription in self._subscriptions.items():
                # Check if handler is still alive
                if subscription.handler not in self._weak_handlers:
                    inactive_subscriptions.append(subscription_id)
                # Check failure rate
                elif subscription.failure_count >= subscription.max_failures:
                    subscription.is_active = False

        # Remove inactive subscriptions
        for subscription_id in inactive_subscriptions:
            if self.remove_subscription(subscription_id):
                removed_count += 1

        return removed_count


class EventDeliveryGuarantee:
    """
    Provides delivery guarantees for event dispatching.

    Implements retry logic, dead letter queues, and delivery confirmation
    to ensure reliable event delivery.
    """

    def __init__(self, config: DispatcherConfig):
        """Initialize delivery guarantee manager."""
        self._config = config
        self._pending_events: Dict[str, QueuedEvent] = {}
        self._retry_queue: deque = deque()
        self._dead_letter_queue: deque = deque(maxlen=1000)
        self._lock = threading.RLock()
        self._logger = get_log_manager().get_logger(__name__)

    def track_event(self, event: Event, subscription_ids: List[str]) -> None:
        """Track an event for delivery guarantee."""
        if not self._config.enable_retry:
            return

        queued_event = QueuedEvent(
            event=event,
            subscription_ids=subscription_ids,
            max_retries=self._config.max_retry_attempts
        )

        with self._lock:
            self._pending_events[event.event_id] = queued_event

    def confirm_delivery(self, event_id: str, subscription_id: str) -> None:
        """Confirm successful delivery to a subscription."""
        with self._lock:
            if event_id in self._pending_events:
                queued_event = self._pending_events[event_id]
                if subscription_id in queued_event.subscription_ids:
                    queued_event.subscription_ids.remove(subscription_id)

                # Remove if all deliveries confirmed
                if not queued_event.subscription_ids:
                    del self._pending_events[event_id]

    def mark_delivery_failed(self, event_id: str, subscription_id: str) -> None:
        """Mark delivery as failed for a subscription."""
        with self._lock:
            if event_id in self._pending_events:
                queued_event = self._pending_events[event_id]

                # Schedule retry if within limits
                if queued_event.retry_count < queued_event.max_retries:
                    queued_event.retry_count += 1
                    queued_event.last_attempt = datetime.now(timezone.utc)
                    queued_event.next_retry = datetime.now(timezone.utc).replace(
                        microsecond=0
                    ) + timedelta(seconds=self._config.retry_delay_seconds * queued_event.retry_count)

                    self._retry_queue.append(queued_event)
                else:
                    # Move to dead letter queue
                    self._dead_letter_queue.append(queued_event)
                    if subscription_id in queued_event.subscription_ids:
                        queued_event.subscription_ids.remove(subscription_id)

                    # Remove if no more pending subscriptions
                    if not queued_event.subscription_ids:
                        del self._pending_events[event_id]

    def get_events_for_retry(self) -> List[QueuedEvent]:
        """Get events that are ready for retry."""
        ready_events = []
        current_time = datetime.now(timezone.utc)

        with self._lock:
            events_to_remove = []

            for queued_event in self._retry_queue:
                if queued_event.next_retry and current_time >= queued_event.next_retry:
                    ready_events.append(queued_event)
                    events_to_remove.append(queued_event)

            # Remove from retry queue
            for event in events_to_remove:
                try:
                    self._retry_queue.remove(event)
                except ValueError:
                    pass

        return ready_events

    def get_pending_count(self) -> int:
        """Get count of pending events."""
        with self._lock:
            return len(self._pending_events)

    def get_retry_queue_size(self) -> int:
        """Get size of retry queue."""
        with self._lock:
            return len(self._retry_queue)

    def get_dead_letter_queue_size(self) -> int:
        """Get size of dead letter queue."""
        with self._lock:
            return len(self._dead_letter_queue)


class EventDispatcher:
    """
    Main event dispatcher for routing events to appropriate handlers.

    Provides comprehensive event dispatching with filtering, routing,
    priority management, and delivery guarantees.
    """

    def __init__(self, config: Optional[DispatcherConfig] = None):
        """Initialize the event dispatcher."""
        self._config = config or DispatcherConfig()
        self._logger = get_log_manager().get_logger(__name__)
        self._validation_engine = ValidationEngine()

        # Core components
        self._router = EventRouter()
        self._subscription_manager = EventSubscriptionManager()
        self._delivery_guarantee = EventDeliveryGuarantee(self._config)

        # State management
        self._is_running = False
        self._lock = threading.RLock()
        self._metrics_lock = threading.RLock()

        # Event queues
        self._event_queue: deque = deque(maxlen=self._config.max_queue_size)
        self._priority_queues: Dict[EventPriority, deque] = {
            priority: deque() for priority in EventPriority
        }

        # Metrics and monitoring
        self._metrics = DispatcherMetrics()
        self._start_time = datetime.now(timezone.utc)

        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._dispatch_task: Optional[asyncio.Task] = None
        self._retry_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

        self._logger.info("Event dispatcher initialized")

    async def start(self) -> DispatchResult:
        """Start the event dispatcher."""
        start_time = time.time()

        try:
            with self._lock:
                if self._is_running:
                    return DispatchResult(
                        success=False,
                        message="Event dispatcher is already running"
                    )

                self._is_running = True
                self._start_time = datetime.now(timezone.utc)

                # Start background tasks
                self._dispatch_task = asyncio.create_task(self._dispatch_loop())

                if self._config.enable_retry:
                    self._retry_task = asyncio.create_task(self._retry_loop())

                if self._config.cleanup_interval_seconds > 0:
                    self._cleanup_task = asyncio.create_task(self._cleanup_loop())

                self._logger.info("Event dispatcher started")

                return DispatchResult(
                    success=True,
                    message="Event dispatcher started successfully",
                    processing_time_ms=(time.time() - start_time) * 1000
                )

        except Exception as e:
            self._logger.error(f"Error starting event dispatcher: {e}")
            return DispatchResult(
                success=False,
                message=f"Failed to start event dispatcher: {e}",
                processing_time_ms=(time.time() - start_time) * 1000
            )

    async def stop(self) -> DispatchResult:
        """Stop the event dispatcher."""
        start_time = time.time()

        try:
            with self._lock:
                if not self._is_running:
                    return DispatchResult(
                        success=False,
                        message="Event dispatcher is not running"
                    )

                self._is_running = False

                # Cancel background tasks
                tasks_to_cancel = [
                    self._dispatch_task,
                    self._retry_task,
                    self._cleanup_task
                ]

                for task in tasks_to_cancel:
                    if task:
                        task.cancel()

                # Wait for tasks to complete
                for task in tasks_to_cancel:
                    if task:
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

                # Cancel other background tasks
                for task in self._background_tasks:
                    task.cancel()

                if self._background_tasks:
                    await asyncio.gather(*self._background_tasks, return_exceptions=True)

                self._background_tasks.clear()

                self._logger.info("Event dispatcher stopped")

                return DispatchResult(
                    success=True,
                    message="Event dispatcher stopped successfully",
                    processing_time_ms=(time.time() - start_time) * 1000
                )

        except Exception as e:
            self._logger.error(f"Error stopping event dispatcher: {e}")
            return DispatchResult(
                success=False,
                message=f"Failed to stop event dispatcher: {e}",
                processing_time_ms=(time.time() - start_time) * 1000
            )

    async def dispatch_event(self, event: Event) -> DispatchResult:
        """Dispatch an event to appropriate handlers."""
        start_time = time.time()

        try:
            if not self._is_running:
                return DispatchResult(
                    success=False,
                    event_id=event.event_id,
                    message="Event dispatcher is not running"
                )

            # Validate event
            if not self._validate_event(event):
                return DispatchResult(
                    success=False,
                    event_id=event.event_id,
                    message="Invalid event format"
                )

            # Add to appropriate queue
            if self._config.enable_priority_queue:
                self._priority_queues[event.priority].append(event)
            else:
                self._event_queue.append(event)

            # Update metrics
            with self._metrics_lock:
                self._metrics.events_received += 1
                self._metrics.queue_size = len(self._event_queue)
                if self._metrics.queue_size > self._metrics.peak_queue_size:
                    self._metrics.peak_queue_size = self._metrics.queue_size

            return DispatchResult(
                success=True,
                event_id=event.event_id,
                message="Event queued for dispatch",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            self._logger.error(f"Error dispatching event: {e}")
            return DispatchResult(
                success=False,
                event_id=event.event_id,
                message=f"Failed to dispatch event: {e}",
                processing_time_ms=(time.time() - start_time) * 1000
            )

    def subscribe(
        self,
        handler: IEventHandler,
        event_types: Optional[Set[EventType]] = None,
        sources: Optional[Set[str]] = None,
        filters: Optional[List[EventFilter]] = None,
        priority: int = 0
    ) -> str:
        """Subscribe a handler to events."""
        return self._subscription_manager.add_subscription(
            handler=handler,
            event_types=event_types,
            sources=sources,
            filters=filters,
            priority=priority
        )

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe a handler."""
        return self._subscription_manager.remove_subscription(subscription_id)

    def add_route(self, route: EventRoute) -> bool:
        """Add a routing rule."""
        return self._router.add_route(route)

    def remove_route(self, route_id: str) -> bool:
        """Remove a routing rule."""
        return self._router.remove_route(route_id)

    def add_filter(self, filter_config: EventFilter) -> bool:
        """Add an event filter."""
        return self._router.add_filter(filter_config)

    def remove_filter(self, filter_id: str) -> bool:
        """Remove an event filter."""
        return self._router.remove_filter(filter_id)

    def get_metrics(self) -> DispatcherMetrics:
        """Get current dispatcher metrics."""
        with self._metrics_lock:
            # Update uptime
            self._metrics.uptime_seconds = (
                datetime.now(timezone.utc) - self._start_time
            ).total_seconds()

            # Update queue size
            self._metrics.queue_size = len(self._event_queue)
            self._metrics.active_subscriptions = len(self._subscription_manager.list_subscriptions())

            return self._metrics

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

    async def _dispatch_loop(self) -> None:
        """Main dispatch loop."""
        while self._is_running:
            try:
                # Process priority queues first
                if self._config.enable_priority_queue:
                    await self._process_priority_queues()
                else:
                    await self._process_regular_queue()

                # Small delay to prevent busy waiting
                await asyncio.sleep(0.001)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in dispatch loop: {e}")
                await asyncio.sleep(1.0)

    async def _process_priority_queues(self) -> None:
        """Process events from priority queues."""
        # Process in priority order
        for priority in sorted(EventPriority, key=lambda p: p.value, reverse=True):
            queue = self._priority_queues[priority]

            batch_count = 0
            while queue and batch_count < self._config.batch_size:
                event = queue.popleft()
                await self._process_single_event(event)
                batch_count += 1

    async def _process_regular_queue(self) -> None:
        """Process events from regular queue."""
        batch_count = 0
        while self._event_queue and batch_count < self._config.batch_size:
            event = self._event_queue.popleft()
            await self._process_single_event(event)
            batch_count += 1

    async def _process_single_event(self, event: Event) -> None:
        """Process a single event."""
        try:
            # Get matching subscriptions
            subscriptions = self._subscription_manager.get_matching_subscriptions(event)

            if not subscriptions:
                with self._metrics_lock:
                    self._metrics.events_filtered += 1
                return

            # Extract handler IDs for routing
            handler_ids = [s.subscription_id for s in subscriptions]

            # Apply routing
            if self._config.enable_routing:
                selected_handlers = self._router.route_event(event, handler_ids)
                subscriptions = [s for s in subscriptions if s.subscription_id in selected_handlers]

            # Track for delivery guarantee
            if self._config.enable_retry:
                subscription_ids = [s.subscription_id for s in subscriptions]
                self._delivery_guarantee.track_event(event, subscription_ids)

            # Dispatch to handlers
            dispatch_tasks = []
            for subscription in subscriptions:
                task = asyncio.create_task(
                    self._dispatch_to_handler(event, subscription)
                )
                dispatch_tasks.append(task)

            # Wait for all dispatches to complete
            if dispatch_tasks:
                await asyncio.gather(*dispatch_tasks, return_exceptions=True)

            # Update metrics
            with self._metrics_lock:
                self._metrics.events_dispatched += 1

        except Exception as e:
            self._logger.error(f"Error processing event {event.event_id}: {e}")
            with self._metrics_lock:
                self._metrics.events_failed += 1

    async def _dispatch_to_handler(self, event: Event, subscription: EventSubscription) -> None:
        """Dispatch event to a specific handler."""
        try:
            # Update handler load
            self._router.update_handler_load(subscription.subscription_id, 1)

            # Call handler
            await subscription.handler.handle_event(event)

            # Update subscription metrics
            subscription.delivery_count += 1
            subscription.last_activity = datetime.now(timezone.utc)

            # Confirm delivery
            if self._config.enable_retry:
                self._delivery_guarantee.confirm_delivery(event.event_id, subscription.subscription_id)

        except Exception as e:
            self._logger.warning(f"Handler failed for event {event.event_id}: {e}")

            # Update failure metrics
            subscription.failure_count += 1

            # Mark delivery as failed
            if self._config.enable_retry:
                self._delivery_guarantee.mark_delivery_failed(event.event_id, subscription.subscription_id)

            # Deactivate subscription if too many failures
            if subscription.failure_count >= subscription.max_failures:
                subscription.is_active = False

        finally:
            # Update handler load
            self._router.update_handler_load(subscription.subscription_id, -1)

    async def _retry_loop(self) -> None:
        """Retry loop for failed deliveries."""
        while self._is_running:
            try:
                # Get events ready for retry
                retry_events = self._delivery_guarantee.get_events_for_retry()

                for queued_event in retry_events:
                    # Re-queue for dispatch
                    if self._config.enable_priority_queue:
                        self._priority_queues[queued_event.event.priority].append(queued_event.event)
                    else:
                        self._event_queue.append(queued_event.event)

                    with self._metrics_lock:
                        self._metrics.events_retried += 1

                # Sleep before next retry check
                await asyncio.sleep(self._config.retry_delay_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in retry loop: {e}")
                await asyncio.sleep(1.0)

    async def _cleanup_loop(self) -> None:
        """Cleanup loop for maintenance tasks."""
        while self._is_running:
            try:
                await asyncio.sleep(self._config.cleanup_interval_seconds)

                if not self._is_running:
                    break

                # Clean up inactive subscriptions
                removed_count = self._subscription_manager.cleanup_inactive_subscriptions()
                if removed_count > 0:
                    self._logger.debug(f"Cleaned up {removed_count} inactive subscriptions")

                # Update metrics
                self._update_metrics()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(1.0)

    def _update_metrics(self) -> None:
        """Update metrics."""
        try:
            with self._metrics_lock:
                self._metrics.queue_size = len(self._event_queue)
                self._metrics.active_subscriptions = len(self._subscription_manager.list_subscriptions())

        except Exception as e:
            self._logger.error(f"Error updating metrics: {e}")
