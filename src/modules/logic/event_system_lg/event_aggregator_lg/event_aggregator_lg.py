"""
Module: event_aggregator_lg
Description: Batches and aggregates events for efficient processing with time windows and priority handling
Phase: 4
Location: /src/modules/logic/event_system_lg/event_aggregator_lg/event_aggregator_lg.py
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
    IEventAggregator, IEventHandler, Event, EventType, EventPriority,
    EventStatus, AggregationStrategy, EventBatch, AggregationResult
)
from src.modules.logic.state_management_lg.app_state_manager_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg import ValidationEngine


class WindowType(Enum):
    """Types of aggregation windows."""
    TIME_BASED = "time_based"
    COUNT_BASED = "count_based"
    SIZE_BASED = "size_based"
    HYBRID = "hybrid"


class AggregationMode(Enum):
    """Aggregation modes."""
    BATCH = "batch"
    STREAM = "stream"
    SLIDING_WINDOW = "sliding_window"
    TUMBLING_WINDOW = "tumbling_window"


@dataclass
class AggregationWindow:
    """Aggregation window configuration and state."""
    window_id: str
    window_type: WindowType
    aggregation_key: str
    events: List[Event] = field(default_factory=list)
    max_size: int = 100
    max_duration_ms: float = 1000.0
    max_memory_bytes: int = 1024 * 1024  # 1MB
    created_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_closed: bool = False
    priority: EventPriority = EventPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_event(self, event: Event) -> bool:
        """Add event to window."""
        if self.is_closed:
            return False
        
        self.events.append(event)
        self.last_updated = datetime.now(timezone.utc)
        
        # Update priority to highest event priority
        if event.priority.value > self.priority.value:
            self.priority = event.priority
        
        return True
    
    def should_close(self) -> bool:
        """Check if window should be closed."""
        if self.is_closed:
            return True
        
        current_time = datetime.now(timezone.utc)
        
        # Check count limit
        if len(self.events) >= self.max_size:
            return True
        
        # Check time limit
        duration_ms = (current_time - self.created_timestamp).total_seconds() * 1000
        if duration_ms >= self.max_duration_ms:
            return True
        
        # Check memory limit (approximate)
        estimated_size = sum(len(str(event.data)) for event in self.events)
        if estimated_size >= self.max_memory_bytes:
            return True
        
        return False
    
    def close(self) -> EventBatch:
        """Close window and create batch."""
        self.is_closed = True
        
        return EventBatch(
            batch_id=self.window_id,
            events=self.events.copy(),
            batch_size=len(self.events),
            created_timestamp=self.created_timestamp,
            aggregation_strategy=AggregationStrategy.TIME_WINDOW,
            priority=self.priority,
            metadata=self.metadata.copy()
        )


@dataclass
class EventSubscription:
    """Event subscription for aggregation."""
    subscription_id: str
    handler: IEventHandler
    event_types: Set[EventType] = field(default_factory=set)
    sources: Set[str] = field(default_factory=set)
    aggregation_keys: Set[str] = field(default_factory=set)
    priority: int = 0
    is_active: bool = True
    created_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    delivery_count: int = 0
    failure_count: int = 0
    max_failures: int = 5


@dataclass
class QueuedEvent:
    """Queued event for aggregation."""
    event: Event
    aggregation_key: str
    priority: EventPriority
    queued_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class AggregatorConfig:
    """Configuration for the event aggregator."""
    max_windows: int = 1000
    default_window_size: int = 100
    default_window_duration_ms: float = 1000.0
    default_window_memory_bytes: int = 1024 * 1024  # 1MB
    max_queue_size: int = 10000
    enable_priority_aggregation: bool = True
    enable_adaptive_windows: bool = True
    enable_compression: bool = False
    cleanup_interval_seconds: float = 300.0
    metrics_enabled: bool = True
    window_overlap_percent: float = 0.0  # For sliding windows
    aggregation_mode: AggregationMode = AggregationMode.TUMBLING_WINDOW


@dataclass
class AggregatorMetrics:
    """Metrics for event aggregator operations."""
    events_received: int = 0
    events_aggregated: int = 0
    events_delivered: int = 0
    events_failed: int = 0
    batches_created: int = 0
    batches_delivered: int = 0
    active_windows: int = 0
    active_subscriptions: int = 0
    queue_size: int = 0
    average_batch_size: float = 0.0
    average_window_duration_ms: float = 0.0
    peak_queue_size: int = 0
    total_processing_time_ms: float = 0.0
    uptime_seconds: float = 0.0


class EventBatcher:
    """
    Event batching engine for creating aggregation windows.
    
    Manages time-based and count-based windows for efficient
    event aggregation and processing.
    """
    
    def __init__(self, config: AggregatorConfig):
        """Initialize the event batcher."""
        self._config = config
        self._windows: Dict[str, AggregationWindow] = {}
        self._aggregation_keys: Dict[str, Set[str]] = defaultdict(set)  # key -> window_ids
        self._lock = threading.RLock()
        self._logger = get_log_manager().get_logger(__name__)
    
    def add_event(self, event: Event) -> Optional[EventBatch]:
        """Add event to appropriate window."""
        with self._lock:
            # Determine aggregation key
            aggregation_key = self._get_aggregation_key(event)
            
            # Find or create window
            window = self._get_or_create_window(aggregation_key, event)
            
            # Add event to window
            if window.add_event(event):
                event.status = EventStatus.AGGREGATED
                
                # Check if window should be closed
                if window.should_close():
                    return self._close_window(window.window_id)
            
            return None
    
    def force_close_windows(self, max_age_seconds: float = None) -> List[EventBatch]:
        """Force close windows based on age or other criteria."""
        batches = []
        current_time = datetime.now(timezone.utc)
        windows_to_close = []
        
        with self._lock:
            for window_id, window in self._windows.items():
                should_close = False
                
                if max_age_seconds:
                    age_seconds = (current_time - window.created_timestamp).total_seconds()
                    if age_seconds >= max_age_seconds:
                        should_close = True
                else:
                    # Use default window duration
                    if window.should_close():
                        should_close = True
                
                if should_close and not window.is_closed:
                    windows_to_close.append(window_id)
            
            # Close windows
            for window_id in windows_to_close:
                batch = self._close_window(window_id)
                if batch:
                    batches.append(batch)
        
        return batches
    
    def get_window_count(self) -> int:
        """Get current number of active windows."""
        with self._lock:
            return len([w for w in self._windows.values() if not w.is_closed])
    
    def cleanup_closed_windows(self) -> int:
        """Clean up closed windows."""
        removed_count = 0
        
        with self._lock:
            closed_windows = [
                window_id for window_id, window in self._windows.items()
                if window.is_closed
            ]
            
            for window_id in closed_windows:
                window = self._windows[window_id]
                
                # Remove from aggregation key index
                self._aggregation_keys[window.aggregation_key].discard(window_id)
                if not self._aggregation_keys[window.aggregation_key]:
                    del self._aggregation_keys[window.aggregation_key]
                
                # Remove window
                del self._windows[window_id]
                removed_count += 1
        
        return removed_count

    def _get_aggregation_key(self, event: Event) -> str:
        """Get aggregation key for an event."""
        # Use event's aggregation key if provided
        if event.aggregation_key:
            return event.aggregation_key

        # Default aggregation by event type and source
        return f"{event.event_type.value}:{event.source}"

    def _get_or_create_window(self, aggregation_key: str, event: Event) -> AggregationWindow:
        """Get existing window or create new one."""
        # Check for existing active window
        window_ids = self._aggregation_keys.get(aggregation_key, set())

        for window_id in window_ids:
            window = self._windows.get(window_id)
            if window and not window.is_closed:
                return window

        # Create new window
        window_id = str(uuid.uuid4())
        window = AggregationWindow(
            window_id=window_id,
            window_type=WindowType.HYBRID,
            aggregation_key=aggregation_key,
            max_size=self._config.default_window_size,
            max_duration_ms=self._config.default_window_duration_ms,
            max_memory_bytes=self._config.default_window_memory_bytes,
            priority=event.priority
        )

        self._windows[window_id] = window
        self._aggregation_keys[aggregation_key].add(window_id)

        return window

    def _close_window(self, window_id: str) -> Optional[EventBatch]:
        """Close a window and return batch."""
        window = self._windows.get(window_id)
        if not window or window.is_closed:
            return None

        batch = window.close()
        return batch


class PriorityManager:
    """
    Priority management for event aggregation.

    Manages priority-based queues and ensures high-priority
    events are processed with appropriate urgency.
    """

    def __init__(self):
        """Initialize the priority manager."""
        self._priority_queues: Dict[EventPriority, deque] = {
            priority: deque() for priority in EventPriority
        }
        self._lock = threading.RLock()
        self._logger = get_log_manager().get_logger(__name__)

    def add_event(self, event: Event) -> None:
        """Add event to priority queue."""
        with self._lock:
            queued_event = QueuedEvent(
                event=event,
                aggregation_key=event.aggregation_key or f"{event.event_type.value}:{event.source}",
                priority=event.priority
            )
            self._priority_queues[event.priority].append(queued_event)

    def get_next_events(self, max_count: int = 10) -> List[QueuedEvent]:
        """Get next events to process, prioritized."""
        events = []

        with self._lock:
            # Process in priority order
            for priority in sorted(EventPriority, key=lambda p: p.value, reverse=True):
                queue = self._priority_queues[priority]

                while queue and len(events) < max_count:
                    events.append(queue.popleft())

        return events

    def get_queue_sizes(self) -> Dict[EventPriority, int]:
        """Get sizes of priority queues."""
        with self._lock:
            return {priority: len(queue) for priority, queue in self._priority_queues.items()}

    def clear_queues(self) -> None:
        """Clear all priority queues."""
        with self._lock:
            for queue in self._priority_queues.values():
                queue.clear()


class DeliveryScheduler:
    """
    Delivery scheduler for event batches.

    Manages scheduling and delivery of aggregated event batches
    to subscribed handlers with timing and retry logic.
    """

    def __init__(self, config: AggregatorConfig):
        """Initialize the delivery scheduler."""
        self._config = config
        self._scheduled_batches: deque = deque()
        self._delivery_queue: deque = deque()
        self._lock = threading.RLock()
        self._logger = get_log_manager().get_logger(__name__)

    def schedule_batch(self, batch: EventBatch) -> None:
        """Schedule a batch for delivery."""
        with self._lock:
            self._scheduled_batches.append(batch)

    def get_ready_batches(self) -> List[EventBatch]:
        """Get batches ready for delivery."""
        ready_batches = []

        with self._lock:
            # For now, all scheduled batches are ready
            # In future, could add delay scheduling
            while self._scheduled_batches:
                ready_batches.append(self._scheduled_batches.popleft())

        return ready_batches

    def get_scheduled_count(self) -> int:
        """Get count of scheduled batches."""
        with self._lock:
            return len(self._scheduled_batches)


class EventAggregator(IEventAggregator):
    """
    Main event aggregator for batching and aggregating events.

    Provides comprehensive event aggregation with time windows,
    priority management, and efficient batch delivery.
    """

    def __init__(self, config: Optional[AggregatorConfig] = None):
        """Initialize the event aggregator."""
        self._config = config or AggregatorConfig()
        self._logger = get_log_manager().get_logger(__name__)
        self._validation_engine = ValidationEngine()

        # Core components
        self._event_batcher = EventBatcher(self._config)
        self._priority_manager = PriorityManager()
        self._delivery_scheduler = DeliveryScheduler(self._config)

        # State management
        self._is_running = False
        self._lock = threading.RLock()
        self._metrics_lock = threading.RLock()

        # Subscription management
        self._subscriptions: Dict[str, EventSubscription] = {}
        self._event_type_index: Dict[EventType, Set[str]] = defaultdict(set)
        self._source_index: Dict[str, Set[str]] = defaultdict(set)
        self._aggregation_key_index: Dict[str, Set[str]] = defaultdict(set)

        # Metrics and monitoring
        self._metrics = AggregatorMetrics()
        self._start_time = datetime.now(timezone.utc)

        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._aggregation_task: Optional[asyncio.Task] = None
        self._delivery_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

        # Weak references to prevent memory leaks
        self._weak_handlers: WeakSet = WeakSet()

        self._logger.info("Event aggregator initialized")

    async def start(self) -> AggregationResult:
        """Start the event aggregator."""
        start_time = time.time()

        try:
            with self._lock:
                if self._is_running:
                    return AggregationResult(
                        batch_id="",
                        success=False,
                        metadata={'message': "Event aggregator is already running"}
                    )

                self._is_running = True
                self._start_time = datetime.now(timezone.utc)

                # Start background tasks
                self._aggregation_task = asyncio.create_task(self._aggregation_loop())
                self._delivery_task = asyncio.create_task(self._delivery_loop())

                if self._config.cleanup_interval_seconds > 0:
                    self._cleanup_task = asyncio.create_task(self._cleanup_loop())

                self._logger.info("Event aggregator started")

                return AggregationResult(
                    batch_id="",
                    success=True,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    metadata={'message': "Event aggregator started successfully"}
                )

        except Exception as e:
            self._logger.error(f"Error starting event aggregator: {e}")
            return AggregationResult(
                batch_id="",
                success=False,
                processing_time_ms=(time.time() - start_time) * 1000,
                metadata={'message': f"Failed to start event aggregator: {e}"}
            )

    async def stop(self) -> AggregationResult:
        """Stop the event aggregator."""
        start_time = time.time()

        try:
            with self._lock:
                if not self._is_running:
                    return AggregationResult(
                        batch_id="",
                        success=False,
                        metadata={'message': "Event aggregator is not running"}
                    )

                self._is_running = False

                # Cancel background tasks
                tasks_to_cancel = [
                    self._aggregation_task,
                    self._delivery_task,
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

                self._logger.info("Event aggregator stopped")

                return AggregationResult(
                    batch_id="",
                    success=True,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    metadata={'message': "Event aggregator stopped successfully"}
                )

        except Exception as e:
            self._logger.error(f"Error stopping event aggregator: {e}")
            return AggregationResult(
                batch_id="",
                success=False,
                processing_time_ms=(time.time() - start_time) * 1000,
                metadata={'message': f"Failed to stop event aggregator: {e}"}
            )

    async def aggregate_event(self, event: Event) -> AggregationResult:
        """Aggregate an event into batches."""
        start_time = time.time()

        try:
            if not self._is_running:
                return AggregationResult(
                    batch_id="",
                    success=False,
                    metadata={'message': "Event aggregator is not running"}
                )

            # Validate event
            if not self._validate_event(event):
                return AggregationResult(
                    batch_id="",
                    success=False,
                    metadata={'message': "Invalid event format"}
                )

            # Set event status
            event.status = EventStatus.PROCESSING

            # Add to priority manager
            self._priority_manager.add_event(event)

            # Update metrics
            with self._metrics_lock:
                self._metrics.events_received += 1
                queue_sizes = self._priority_manager.get_queue_sizes()
                self._metrics.queue_size = sum(queue_sizes.values())
                if self._metrics.queue_size > self._metrics.peak_queue_size:
                    self._metrics.peak_queue_size = self._metrics.queue_size

            return AggregationResult(
                batch_id="",
                success=True,
                events_aggregated=1,
                processing_time_ms=(time.time() - start_time) * 1000,
                metadata={'message': "Event queued for aggregation"}
            )

        except Exception as e:
            self._logger.error(f"Error aggregating event: {e}")
            return AggregationResult(
                batch_id="",
                success=False,
                processing_time_ms=(time.time() - start_time) * 1000,
                metadata={'message': f"Failed to aggregate event: {e}"}
            )

    def subscribe(
        self,
        handler: IEventHandler,
        event_types: Optional[Set[EventType]] = None,
        sources: Optional[Set[str]] = None,
        aggregation_keys: Optional[Set[str]] = None,
        priority: int = 0
    ) -> str:
        """Subscribe a handler to aggregated events."""
        try:
            subscription_id = str(uuid.uuid4())

            subscription = EventSubscription(
                subscription_id=subscription_id,
                handler=handler,
                event_types=event_types or set(),
                sources=sources or set(),
                aggregation_keys=aggregation_keys or set(),
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

                # Index by aggregation keys
                if aggregation_keys:
                    for key in aggregation_keys:
                        self._aggregation_key_index[key].add(subscription_id)

                # Update metrics
                with self._metrics_lock:
                    self._metrics.active_subscriptions += 1

            # Add to weak references
            self._weak_handlers.add(handler)

            self._logger.debug(f"Aggregation subscription created: {subscription_id}")
            return subscription_id

        except Exception as e:
            self._logger.error(f"Error creating aggregation subscription: {e}")
            raise

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe a handler."""
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

                if subscription.aggregation_keys:
                    for key in subscription.aggregation_keys:
                        self._aggregation_key_index[key].discard(subscription_id)

                # Remove subscription
                del self._subscriptions[subscription_id]

                # Update metrics
                with self._metrics_lock:
                    self._metrics.active_subscriptions -= 1

            self._logger.debug(f"Aggregation subscription removed: {subscription_id}")
            return True

        except Exception as e:
            self._logger.error(f"Error removing aggregation subscription: {e}")
            return False

    def get_metrics(self) -> AggregatorMetrics:
        """Get current aggregator metrics."""
        with self._metrics_lock:
            # Update uptime
            self._metrics.uptime_seconds = (
                datetime.now(timezone.utc) - self._start_time
            ).total_seconds()

            # Update active windows
            self._metrics.active_windows = self._event_batcher.get_window_count()

            # Update queue size
            queue_sizes = self._priority_manager.get_queue_sizes()
            self._metrics.queue_size = sum(queue_sizes.values())

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

    async def _aggregation_loop(self) -> None:
        """Main aggregation loop."""
        while self._is_running:
            try:
                # Get next events to process
                events = self._priority_manager.get_next_events(max_count=50)

                if not events:
                    await asyncio.sleep(0.01)  # Small delay when no events
                    continue

                # Process events through batcher
                for queued_event in events:
                    batch = self._event_batcher.add_event(queued_event.event)

                    if batch:
                        # Schedule batch for delivery
                        self._delivery_scheduler.schedule_batch(batch)

                        with self._metrics_lock:
                            self._metrics.batches_created += 1
                            self._metrics.events_aggregated += batch.batch_size

                            # Update average batch size
                            total_batches = self._metrics.batches_created
                            current_avg = self._metrics.average_batch_size
                            self._metrics.average_batch_size = (
                                (current_avg * (total_batches - 1) + batch.batch_size) / total_batches
                            )

                # Force close old windows periodically
                if len(events) == 0:  # Only when queue is empty
                    batches = self._event_batcher.force_close_windows(max_age_seconds=5.0)
                    for batch in batches:
                        self._delivery_scheduler.schedule_batch(batch)

                        with self._metrics_lock:
                            self._metrics.batches_created += 1
                            self._metrics.events_aggregated += batch.batch_size

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in aggregation loop: {e}")
                await asyncio.sleep(1.0)

    async def _delivery_loop(self) -> None:
        """Delivery loop for aggregated batches."""
        while self._is_running:
            try:
                # Get ready batches
                ready_batches = self._delivery_scheduler.get_ready_batches()

                if not ready_batches:
                    await asyncio.sleep(0.01)  # Small delay when no batches
                    continue

                # Deliver batches
                for batch in ready_batches:
                    await self._deliver_batch(batch)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in delivery loop: {e}")
                await asyncio.sleep(1.0)

    async def _deliver_batch(self, batch: EventBatch) -> None:
        """Deliver a batch to subscribed handlers."""
        try:
            # Get matching subscriptions
            matching_subscriptions = self._get_matching_subscriptions(batch)

            if not matching_subscriptions:
                return

            # Sort by priority
            sorted_subscriptions = sorted(
                matching_subscriptions,
                key=lambda s: s.priority,
                reverse=True
            )

            # Deliver to handlers
            delivery_tasks = []
            for subscription in sorted_subscriptions:
                if subscription.is_active:
                    task = asyncio.create_task(
                        self._deliver_to_handler(batch, subscription)
                    )
                    delivery_tasks.append(task)

            # Wait for all deliveries
            if delivery_tasks:
                await asyncio.gather(*delivery_tasks, return_exceptions=True)

            # Update metrics
            with self._metrics_lock:
                self._metrics.batches_delivered += 1
                self._metrics.events_delivered += batch.batch_size

        except Exception as e:
            self._logger.error(f"Error delivering batch {batch.batch_id}: {e}")

    async def _deliver_to_handler(self, batch: EventBatch, subscription: EventSubscription) -> None:
        """Deliver batch to a specific handler."""
        try:
            # Call handler for each event in batch
            for event in batch.events:
                await subscription.handler.handle_event(event)

            # Update subscription metrics
            subscription.delivery_count += 1
            subscription.last_activity = datetime.now(timezone.utc)

        except Exception as e:
            self._logger.warning(f"Handler failed for batch {batch.batch_id}: {e}")
            subscription.failure_count += 1

            # Deactivate subscription if too many failures
            if subscription.failure_count >= subscription.max_failures:
                subscription.is_active = False

    def _get_matching_subscriptions(self, batch: EventBatch) -> List[EventSubscription]:
        """Get subscriptions that match a batch."""
        matching_subscriptions = []

        with self._lock:
            # Get all unique event types and sources in batch
            event_types = set(event.event_type for event in batch.events)
            sources = set(event.source for event in batch.events if event.source)
            aggregation_keys = set(event.aggregation_key for event in batch.events if event.aggregation_key)

            subscription_ids = set()

            # Get subscriptions by event types
            for event_type in event_types:
                subscription_ids.update(self._event_type_index.get(event_type, set()))

            # Get subscriptions by sources
            for source in sources:
                subscription_ids.update(self._source_index.get(source, set()))

            # Get subscriptions by aggregation keys
            for key in aggregation_keys:
                subscription_ids.update(self._aggregation_key_index.get(key, set()))

            # Filter and validate subscriptions
            for subscription_id in subscription_ids:
                subscription = self._subscriptions.get(subscription_id)
                if subscription and subscription.is_active:
                    if self._batch_matches_subscription(batch, subscription):
                        matching_subscriptions.append(subscription)

        return matching_subscriptions

    def _batch_matches_subscription(self, batch: EventBatch, subscription: EventSubscription) -> bool:
        """Check if a batch matches a subscription."""
        # Check event types
        if subscription.event_types:
            batch_event_types = set(event.event_type for event in batch.events)
            if not batch_event_types.intersection(subscription.event_types):
                return False

        # Check sources
        if subscription.sources:
            batch_sources = set(event.source for event in batch.events if event.source)
            if not batch_sources.intersection(subscription.sources):
                return False

        # Check aggregation keys
        if subscription.aggregation_keys:
            batch_keys = set(event.aggregation_key for event in batch.events if event.aggregation_key)
            if not batch_keys.intersection(subscription.aggregation_keys):
                return False

        return True

    async def _cleanup_loop(self) -> None:
        """Cleanup loop for maintenance tasks."""
        while self._is_running:
            try:
                await asyncio.sleep(self._config.cleanup_interval_seconds)

                if not self._is_running:
                    break

                # Clean up closed windows
                removed_windows = self._event_batcher.cleanup_closed_windows()
                if removed_windows > 0:
                    self._logger.debug(f"Cleaned up {removed_windows} closed windows")

                # Clean up inactive subscriptions
                await self._cleanup_inactive_subscriptions()

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
                    # Check if handler is still alive
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

    def _update_metrics(self) -> None:
        """Update metrics."""
        try:
            with self._metrics_lock:
                # Update window and queue metrics
                self._metrics.active_windows = self._event_batcher.get_window_count()
                queue_sizes = self._priority_manager.get_queue_sizes()
                self._metrics.queue_size = sum(queue_sizes.values())

        except Exception as e:
            self._logger.error(f"Error updating metrics: {e}")
