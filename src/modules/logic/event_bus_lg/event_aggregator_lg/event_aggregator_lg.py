"""
Module: event_aggregator_lg
Description: Collects and batches events for efficient processing, manages event priorities and delivery guarantees
Phase: 4
Location: /src/modules/logic/event_bus_lg/event_aggregator_lg/event_aggregator_lg.py
"""

# Standard library imports
import asyncio
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Callable, Any
import heapq

# Third-party imports
# None required

# Local imports
from src.modules.logic.event_bus_lg.base_interfaces import (
    IEventAggregator, IEventHandler, Event, EventType, EventPriority,
    EventStatus, AggregationStrategy, EventBatch, AggregationResult, AggregatorConfig
)
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg import ValidationEngine


@dataclass
class EventSubscription:
    """Data structure representing an event subscription."""
    subscription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    handler: IEventHandler = None
    event_types: Set[EventType] = field(default_factory=set)
    sources: Set[str] = field(default_factory=set)
    priority: int = 0
    is_active: bool = True
    created_timestamp: datetime = field(default_factory=datetime.now)
    last_used_timestamp: Optional[datetime] = None
    event_count: int = 0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueuedEvent:
    """Data structure for priority queue events."""
    priority: int
    timestamp: float
    event: Event
    
    def __lt__(self, other):
        # Higher priority first, then older events first
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.timestamp < other.timestamp


@dataclass
class AggregationWindow:
    """Data structure representing an aggregation window."""
    window_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy: AggregationStrategy = AggregationStrategy.TIME_WINDOW
    events: List[Event] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    max_size: int = 100
    time_window_ms: int = 1000
    aggregation_key: Optional[str] = None
    is_closed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def should_close(self) -> bool:
        """Check if window should be closed."""
        if self.is_closed:
            return True
        
        current_time = datetime.now()
        
        # Check size limit
        if len(self.events) >= self.max_size:
            return True
        
        # Check time window
        if self.strategy == AggregationStrategy.TIME_WINDOW:
            elapsed_ms = (current_time - self.start_time).total_seconds() * 1000
            if elapsed_ms >= self.time_window_ms:
                return True
        
        return False
    
    def add_event(self, event: Event) -> bool:
        """Add event to window."""
        if self.is_closed or self.should_close():
            return False
        
        self.events.append(event)
        return True
    
    def close(self) -> EventBatch:
        """Close window and create batch."""
        self.is_closed = True
        self.end_time = datetime.now()
        
        # Determine batch priority
        if self.events:
            max_priority = max(event.priority for event in self.events)
        else:
            max_priority = EventPriority.NORMAL
        
        return EventBatch(
            events=self.events.copy(),
            aggregation_strategy=self.strategy,
            priority=max_priority,
            metadata={
                'window_id': self.window_id,
                'start_time': self.start_time.isoformat(),
                'end_time': self.end_time.isoformat() if self.end_time else None,
                'aggregation_key': self.aggregation_key
            }
        )


class PriorityManager:
    """Manages event priorities and scheduling."""
    
    def __init__(self, config: Optional[AggregatorConfig] = None):
        """Initialize priority manager."""
        self._config = config or AggregatorConfig()
        self._priority_queues: Dict[EventPriority, List[QueuedEvent]] = {
            priority: [] for priority in EventPriority
        }
        self._lock = threading.RLock()
    
    def add_event(self, event: Event) -> None:
        """Add event to priority queue."""
        queued_event = QueuedEvent(
            priority=event.priority.value,
            timestamp=time.time(),
            event=event
        )
        
        with self._lock:
            heapq.heappush(self._priority_queues[event.priority], queued_event)
    
    def get_next_events(self, max_count: int = 10) -> List[Event]:
        """Get next events by priority."""
        events = []
        
        with self._lock:
            # Process in priority order
            for priority in sorted(EventPriority, key=lambda p: p.value, reverse=True):
                queue = self._priority_queues[priority]
                
                while queue and len(events) < max_count:
                    queued_event = heapq.heappop(queue)
                    events.append(queued_event.event)
        
        return events
    
    def get_queue_sizes(self) -> Dict[EventPriority, int]:
        """Get queue sizes by priority."""
        with self._lock:
            return {priority: len(queue) for priority, queue in self._priority_queues.items()}
    
    def clear_expired_events(self, max_age_seconds: float = 300.0) -> int:
        """Clear expired events from queues."""
        current_time = time.time()
        expired_count = 0
        
        with self._lock:
            for priority, queue in self._priority_queues.items():
                # Filter out expired events
                valid_events = []
                for queued_event in queue:
                    if queued_event.event.ttl_seconds is None:
                        valid_events.append(queued_event)
                    elif (current_time - queued_event.timestamp) < queued_event.event.ttl_seconds:
                        valid_events.append(queued_event)
                    else:
                        expired_count += 1
                
                # Rebuild heap
                self._priority_queues[priority] = valid_events
                heapq.heapify(self._priority_queues[priority])
        
        return expired_count


class EventBatcher:
    """Manages event batching and aggregation windows."""
    
    def __init__(self, config: Optional[AggregatorConfig] = None):
        """Initialize event batcher."""
        self._config = config or AggregatorConfig()
        self._windows: Dict[str, AggregationWindow] = {}
        self._completed_batches: deque = deque(maxlen=1000)
        self._lock = threading.RLock()
    
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
    
    def force_close_windows(self, max_age_ms: Optional[int] = None) -> List[EventBatch]:
        """Force close windows based on age."""
        if max_age_ms is None:
            max_age_ms = self._config.time_window_ms
        
        current_time = datetime.now()
        batches = []
        
        with self._lock:
            windows_to_close = []
            
            for window_id, window in self._windows.items():
                if window.is_closed:
                    continue
                
                elapsed_ms = (current_time - window.start_time).total_seconds() * 1000
                if elapsed_ms >= max_age_ms:
                    windows_to_close.append(window_id)
            
            for window_id in windows_to_close:
                batch = self._close_window(window_id)
                if batch:
                    batches.append(batch)
        
        return batches
    
    def _get_aggregation_key(self, event: Event) -> str:
        """Get aggregation key for event."""
        if event.aggregation_key:
            return event.aggregation_key
        
        # Default aggregation by event type and source
        return f"{event.event_type.value}:{event.source}"
    
    def _get_or_create_window(self, aggregation_key: str, event: Event) -> AggregationWindow:
        """Get existing window or create new one."""
        # Look for existing open window
        for window in self._windows.values():
            if (not window.is_closed and 
                window.aggregation_key == aggregation_key and
                not window.should_close()):
                return window
        
        # Create new window
        window = AggregationWindow(
            strategy=self._config.aggregation_strategy if hasattr(self._config, 'aggregation_strategy') else AggregationStrategy.TIME_WINDOW,
            max_size=self._config.max_batch_size,
            time_window_ms=self._config.time_window_ms,
            aggregation_key=aggregation_key
        )
        
        self._windows[window.window_id] = window
        return window
    
    def _close_window(self, window_id: str) -> Optional[EventBatch]:
        """Close window and create batch."""
        if window_id not in self._windows:
            return None
        
        window = self._windows[window_id]
        if window.is_closed:
            return None
        
        # Create batch
        batch = window.close()
        
        # Store completed batch
        self._completed_batches.append(batch)
        
        # Clean up window
        del self._windows[window_id]
        
        return batch
    
    def get_window_stats(self) -> Dict[str, Any]:
        """Get window statistics."""
        with self._lock:
            active_windows = sum(1 for w in self._windows.values() if not w.is_closed)
            total_events = sum(len(w.events) for w in self._windows.values())
            
            return {
                'active_windows': active_windows,
                'total_windows': len(self._windows),
                'total_events_in_windows': total_events,
                'completed_batches': len(self._completed_batches)
            }


class DeliveryScheduler:
    """Manages delivery scheduling for event batches."""
    
    def __init__(self, config: Optional[AggregatorConfig] = None):
        """Initialize delivery scheduler."""
        self._config = config or AggregatorConfig()
        self._pending_batches: List[EventBatch] = []
        self._delivery_queue: List[EventBatch] = []
        self._lock = threading.RLock()
    
    def schedule_batch(self, batch: EventBatch) -> None:
        """Schedule batch for delivery."""
        with self._lock:
            self._pending_batches.append(batch)
            
            # Sort by priority and creation time
            self._pending_batches.sort(
                key=lambda b: (b.priority.value, b.created_timestamp),
                reverse=True
            )
    
    def get_next_batches(self, max_count: int = 10) -> List[EventBatch]:
        """Get next batches for delivery."""
        with self._lock:
            batches = self._pending_batches[:max_count]
            self._pending_batches = self._pending_batches[max_count:]
            return batches
    
    def get_queue_size(self) -> int:
        """Get pending batch count."""
        with self._lock:
            return len(self._pending_batches)


class EventAggregator(IEventAggregator):
    """
    Production-ready event aggregator for efficient event processing.

    Collects and batches events for efficient processing, manages event
    priorities and delivery guarantees with configurable aggregation strategies.
    """

    def __init__(self,
                 config: Optional[AggregatorConfig] = None,
                 app_state_manager: Optional[AppStateManager] = None):
        """Initialize the event aggregator."""
        self._config = config or AggregatorConfig()
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("event_aggregator")
        self._validation_engine = ValidationEngine()

        # Core components
        self._priority_manager = PriorityManager(self._config)
        self._event_batcher = EventBatcher(self._config)
        self._delivery_scheduler = DeliveryScheduler(self._config)

        # Subscription management
        self._subscriptions: Dict[str, EventSubscription] = {}
        self._type_subscriptions: Dict[EventType, List[str]] = defaultdict(list)
        self._source_subscriptions: Dict[str, List[str]] = defaultdict(list)
        self._subscription_lock = threading.RLock()

        # Processing control
        self._is_running = False
        self._processing_task: Optional[asyncio.Task] = None
        self._aggregation_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

        # Metrics
        self._metrics = {
            'events_aggregated': 0,
            'batches_created': 0,
            'batches_delivered': 0,
            'events_failed': 0,
            'average_batch_size': 0.0,
            'average_processing_time_ms': 0.0,
            'active_subscriptions': 0,
            'pending_events': 0
        }
        self._metrics_lock = threading.RLock()

    async def initialize(self) -> bool:
        """Initialize the event aggregator."""
        try:
            self._logger.info("Initializing event aggregator...")

            # Start processing loops
            self._is_running = True
            self._processing_task = asyncio.create_task(self._processing_loop())
            self._aggregation_task = asyncio.create_task(self._aggregation_loop())

            self._logger.info("Event aggregator initialized successfully")
            return True

        except Exception as e:
            self._logger.error(f"Error initializing event aggregator: {e}")
            return False

    async def shutdown(self) -> bool:
        """Shutdown the event aggregator."""
        try:
            self._logger.info("Shutting down event aggregator...")

            self._is_running = False
            self._shutdown_event.set()

            # Wait for processing tasks
            if self._processing_task:
                await self._processing_task
            if self._aggregation_task:
                await self._aggregation_task

            # Process remaining events
            await self._process_remaining_events()

            self._logger.info("Event aggregator shutdown complete")
            return True

        except Exception as e:
            self._logger.error(f"Error shutting down event aggregator: {e}")
            return False

    async def aggregate_event(self, event: Event) -> AggregationResult:
        """
        Aggregate an event into batches.

        Args:
            event: Event to aggregate

        Returns:
            AggregationResult with aggregation details
        """
        start_time = time.time()
        result = AggregationResult(
            batch_id="",
            success=False
        )

        try:
            # Validate event
            if not self._validate_event(event):
                result.metadata['error'] = "Invalid event format"
                return result

            # Set event status
            event.status = EventStatus.PROCESSING

            # Add to priority manager
            self._priority_manager.add_event(event)

            # Update metrics
            with self._metrics_lock:
                self._metrics['events_aggregated'] += 1
                self._metrics['pending_events'] = sum(
                    self._priority_manager.get_queue_sizes().values()
                )

            result.success = True
            result.events_aggregated = 1

        except Exception as e:
            self._logger.error(f"Error aggregating event {event.event_id}: {e}")
            result.metadata['error'] = str(e)

            with self._metrics_lock:
                self._metrics['events_failed'] += 1

        finally:
            result.processing_time_ms = (time.time() - start_time) * 1000

        return result

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
        try:
            subscription = EventSubscription(
                handler=handler,
                event_types=event_types or set(),
                sources=sources or set()
            )

            with self._subscription_lock:
                self._subscriptions[subscription.subscription_id] = subscription

                # Index by event types
                for event_type in subscription.event_types:
                    self._type_subscriptions[event_type].append(subscription.subscription_id)

                # Index by sources
                for source in subscription.sources:
                    self._source_subscriptions[source].append(subscription.subscription_id)

            self._update_metrics()
            self._logger.debug(f"Added event subscription {subscription.subscription_id}")

            return subscription.subscription_id

        except Exception as e:
            self._logger.error(f"Error adding event subscription: {e}")
            raise

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe a handler.

        Args:
            subscription_id: Subscription identifier

        Returns:
            True if unsubscribed successfully
        """
        try:
            with self._subscription_lock:
                if subscription_id not in self._subscriptions:
                    return False

                subscription = self._subscriptions[subscription_id]

                # Remove from type indexes
                for event_type in subscription.event_types:
                    if subscription_id in self._type_subscriptions[event_type]:
                        self._type_subscriptions[event_type].remove(subscription_id)

                # Remove from source indexes
                for source in subscription.sources:
                    if subscription_id in self._source_subscriptions[source]:
                        self._source_subscriptions[source].remove(subscription_id)

                # Remove subscription
                del self._subscriptions[subscription_id]

            self._update_metrics()
            self._logger.debug(f"Removed event subscription {subscription_id}")

            return True

        except Exception as e:
            self._logger.error(f"Error removing event subscription {subscription_id}: {e}")
            return False

    async def _processing_loop(self) -> None:
        """Main processing loop for event aggregation."""
        self._logger.info("Starting event processing loop")

        while self._is_running:
            try:
                # Get next events from priority manager
                events = self._priority_manager.get_next_events(
                    max_count=self._config.max_batch_size
                )

                if events:
                    await self._process_events(events)

                # Clean up expired events
                expired_count = self._priority_manager.clear_expired_events()
                if expired_count > 0:
                    self._logger.debug(f"Cleaned up {expired_count} expired events")

                # Small delay to prevent busy waiting
                await asyncio.sleep(0.01)

            except Exception as e:
                self._logger.error(f"Error in event processing loop: {e}")
                await asyncio.sleep(1.0)

        self._logger.info("Event processing loop stopped")

    async def _aggregation_loop(self) -> None:
        """Main aggregation loop for batch creation."""
        self._logger.info("Starting event aggregation loop")

        while self._is_running:
            try:
                # Force close old windows
                batches = self._event_batcher.force_close_windows()

                for batch in batches:
                    self._delivery_scheduler.schedule_batch(batch)

                    with self._metrics_lock:
                        self._metrics['batches_created'] += 1

                        # Update average batch size
                        total_batches = self._metrics['batches_created']
                        current_avg = self._metrics['average_batch_size']
                        self._metrics['average_batch_size'] = (
                            (current_avg * (total_batches - 1) + batch.batch_size) / total_batches
                        )

                # Deliver batches
                await self._deliver_batches()

                # Sleep for aggregation window
                await asyncio.sleep(self._config.time_window_ms / 1000.0)

            except Exception as e:
                self._logger.error(f"Error in aggregation loop: {e}")
                await asyncio.sleep(1.0)

        self._logger.info("Event aggregation loop stopped")

    async def _process_events(self, events: List[Event]) -> None:
        """Process a list of events."""
        for event in events:
            try:
                # Add to batcher
                batch = self._event_batcher.add_event(event)

                if batch:
                    # Schedule batch for delivery
                    self._delivery_scheduler.schedule_batch(batch)

                    with self._metrics_lock:
                        self._metrics['batches_created'] += 1

            except Exception as e:
                self._logger.error(f"Error processing event {event.event_id}: {e}")
                event.status = EventStatus.FAILED

                with self._metrics_lock:
                    self._metrics['events_failed'] += 1

    async def _deliver_batches(self) -> None:
        """Deliver batches to subscribers."""
        batches = self._delivery_scheduler.get_next_batches(
            max_count=self._config.max_concurrent_batches
        )

        if not batches:
            return

        # Process batches concurrently
        tasks = [self._deliver_batch(batch) for batch in batches]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _deliver_batch(self, batch: EventBatch) -> None:
        """Deliver a batch to matching subscribers."""
        try:
            # Get matching subscriptions for all events in batch
            all_subscriptions = set()

            for event in batch.events:
                subscriptions = self._get_matching_subscriptions(event)
                all_subscriptions.update(subscriptions)

            # Deliver to each subscription
            for subscription in all_subscriptions:
                try:
                    # Update subscription stats
                    subscription.last_used_timestamp = datetime.now()
                    subscription.event_count += len(batch.events)

                    # Deliver batch
                    for event in batch.events:
                        if subscription.handler.can_handle(event):
                            await subscription.handler.handle_event(event)
                            event.status = EventStatus.DELIVERED

                except Exception as e:
                    self._logger.error(f"Error delivering to subscription {subscription.subscription_id}: {e}")
                    subscription.error_count += 1

                    # Mark events as failed
                    for event in batch.events:
                        if event.status != EventStatus.DELIVERED:
                            event.status = EventStatus.FAILED

            with self._metrics_lock:
                self._metrics['batches_delivered'] += 1

        except Exception as e:
            self._logger.error(f"Error delivering batch {batch.batch_id}: {e}")

    def _get_matching_subscriptions(self, event: Event) -> List[EventSubscription]:
        """Get subscriptions that match an event."""
        matching_subscriptions = []

        with self._subscription_lock:
            # Get subscriptions by event type
            type_subs = self._type_subscriptions.get(event.event_type, [])

            # Get subscriptions by source
            source_subs = self._source_subscriptions.get(event.source, [])

            # Combine and deduplicate
            all_sub_ids = set(type_subs + source_subs)

            for sub_id in all_sub_ids:
                subscription = self._subscriptions.get(sub_id)
                if subscription and subscription.is_active:
                    # Check if subscription matches
                    type_match = (not subscription.event_types or
                                event.event_type in subscription.event_types)
                    source_match = (not subscription.sources or
                                  event.source in subscription.sources)

                    if type_match and source_match:
                        matching_subscriptions.append(subscription)

        return matching_subscriptions

    async def _process_remaining_events(self) -> None:
        """Process remaining events during shutdown."""
        self._logger.info("Processing remaining events...")

        # Process all pending events
        while True:
            events = self._priority_manager.get_next_events(max_count=100)
            if not events:
                break
            await self._process_events(events)

        # Force close all windows and deliver batches
        batches = self._event_batcher.force_close_windows(max_age_ms=0)
        for batch in batches:
            self._delivery_scheduler.schedule_batch(batch)

        # Deliver remaining batches
        await self._deliver_batches()

    def _validate_event(self, event: Event) -> bool:
        """Validate event format and content."""
        try:
            # Basic validation
            if not event.event_id:
                return False

            if not isinstance(event.event_type, EventType):
                return False

            if not isinstance(event.priority, EventPriority):
                return False

            if not event.source:
                return False

            # Use validation engine for detailed validation
            return self._validation_engine.validate_object(event)

        except Exception as e:
            self._logger.error(f"Event validation error: {e}")
            return False

    def _update_metrics(self) -> None:
        """Update aggregator metrics."""
        with self._metrics_lock:
            with self._subscription_lock:
                active_count = sum(1 for s in self._subscriptions.values() if s.is_active)
                self._metrics['active_subscriptions'] = active_count

            # Update pending events count
            self._metrics['pending_events'] = sum(
                self._priority_manager.get_queue_sizes().values()
            )

    def get_metrics(self) -> Dict[str, Any]:
        """Get aggregator metrics."""
        with self._metrics_lock:
            metrics = self._metrics.copy()

            # Add component metrics
            metrics.update({
                'priority_queue_sizes': self._priority_manager.get_queue_sizes(),
                'window_stats': self._event_batcher.get_window_stats(),
                'delivery_queue_size': self._delivery_scheduler.get_queue_size()
            })

            return metrics

    def get_subscription_stats(self) -> Dict[str, Any]:
        """Get subscription statistics."""
        with self._subscription_lock:
            active_count = sum(1 for s in self._subscriptions.values() if s.is_active)
            total_events = sum(s.event_count for s in self._subscriptions.values())
            total_errors = sum(s.error_count for s in self._subscriptions.values())

            return {
                'total_subscriptions': len(self._subscriptions),
                'active_subscriptions': active_count,
                'total_events_processed': total_events,
                'total_errors': total_errors,
                'type_indexes': len(self._type_subscriptions),
                'source_indexes': len(self._source_subscriptions)
            }
