"""
Module: message_dispatcher_lg
Description: Routes messages between application components using publish-subscribe pattern for loose coupling
Phase: 4
Location: /src/modules/logic/event_bus_lg/message_dispatcher_lg/message_dispatcher_lg.py
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
    IMessageDispatcher, IMessageHandler, Message, MessageType, MessagePriority,
    MessageStatus, DeliveryMode, DispatchResult, DispatcherConfig
)
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg import ValidationEngine


@dataclass
class Subscription:
    """Data structure representing a message subscription."""
    subscription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    handler: IMessageHandler = None
    message_types: Set[MessageType] = field(default_factory=set)
    actions: Set[str] = field(default_factory=set)
    priority: int = 0
    is_active: bool = True
    created_timestamp: datetime = field(default_factory=datetime.now)
    last_used_timestamp: Optional[datetime] = None
    message_count: int = 0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueuedMessage:
    """Data structure for priority queue messages."""
    priority: int
    timestamp: float
    message: Message
    
    def __lt__(self, other):
        # Higher priority first, then older messages first
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.timestamp < other.timestamp


@dataclass
class DeliveryGuarantee:
    """Manages delivery guarantees for messages."""
    
    def __init__(self, config: Optional[DispatcherConfig] = None):
        """Initialize delivery guarantee manager."""
        self._config = config or DispatcherConfig()
        self._pending_messages: Dict[str, Message] = {}
        self._delivery_attempts: Dict[str, int] = {}
        self._dead_letter_queue: deque = deque(maxlen=self._config.dead_letter_queue_size)
        self._lock = threading.RLock()
    
    def track_message(self, message: Message) -> None:
        """Track a message for delivery guarantee."""
        with self._lock:
            self._pending_messages[message.message_id] = message
            self._delivery_attempts[message.message_id] = 0
    
    def mark_delivered(self, message_id: str) -> bool:
        """Mark a message as delivered."""
        with self._lock:
            if message_id in self._pending_messages:
                del self._pending_messages[message_id]
                del self._delivery_attempts[message_id]
                return True
            return False
    
    def mark_failed(self, message_id: str) -> bool:
        """Mark a message delivery as failed."""
        with self._lock:
            if message_id in self._pending_messages:
                self._delivery_attempts[message_id] += 1
                message = self._pending_messages[message_id]
                
                if self._delivery_attempts[message_id] >= message.max_retries:
                    # Move to dead letter queue
                    self._dead_letter_queue.append(message)
                    del self._pending_messages[message_id]
                    del self._delivery_attempts[message_id]
                    return False
                return True
            return False
    
    def get_retry_messages(self) -> List[Message]:
        """Get messages that need retry."""
        with self._lock:
            return list(self._pending_messages.values())
    
    def get_dead_letter_messages(self) -> List[Message]:
        """Get messages in dead letter queue."""
        with self._lock:
            return list(self._dead_letter_queue)


class SubscriptionManager:
    """Manages message subscriptions and routing."""
    
    def __init__(self):
        """Initialize subscription manager."""
        self._subscriptions: Dict[str, Subscription] = {}
        self._type_subscriptions: Dict[MessageType, List[str]] = defaultdict(list)
        self._action_subscriptions: Dict[str, List[str]] = defaultdict(list)
        self._lock = threading.RLock()
    
    def add_subscription(self, handler: IMessageHandler,
                        message_types: Optional[Set[MessageType]] = None,
                        actions: Optional[Set[str]] = None,
                        priority: int = 0) -> str:
        """Add a new subscription."""
        subscription = Subscription(
            handler=handler,
            message_types=message_types or set(),
            actions=actions or set(),
            priority=priority
        )
        
        with self._lock:
            self._subscriptions[subscription.subscription_id] = subscription
            
            # Index by message types
            for msg_type in subscription.message_types:
                self._type_subscriptions[msg_type].append(subscription.subscription_id)
                # Sort by priority
                self._type_subscriptions[msg_type].sort(
                    key=lambda sid: self._subscriptions[sid].priority, reverse=True
                )
            
            # Index by actions
            for action in subscription.actions:
                self._action_subscriptions[action].append(subscription.subscription_id)
                # Sort by priority
                self._action_subscriptions[action].sort(
                    key=lambda sid: self._subscriptions[sid].priority, reverse=True
                )
        
        return subscription.subscription_id
    
    def remove_subscription(self, subscription_id: str) -> bool:
        """Remove a subscription."""
        with self._lock:
            if subscription_id not in self._subscriptions:
                return False
            
            subscription = self._subscriptions[subscription_id]
            
            # Remove from type indexes
            for msg_type in subscription.message_types:
                if subscription_id in self._type_subscriptions[msg_type]:
                    self._type_subscriptions[msg_type].remove(subscription_id)
            
            # Remove from action indexes
            for action in subscription.actions:
                if subscription_id in self._action_subscriptions[action]:
                    self._action_subscriptions[action].remove(subscription_id)
            
            # Remove subscription
            del self._subscriptions[subscription_id]
            return True
    
    def get_matching_subscriptions(self, message: Message) -> List[Subscription]:
        """Get subscriptions that match a message."""
        matching_subscriptions = []
        
        with self._lock:
            # Get subscriptions by message type
            type_subs = self._type_subscriptions.get(message.message_type, [])
            
            # Get subscriptions by action
            action_subs = self._action_subscriptions.get(message.action, [])
            
            # Combine and deduplicate
            all_sub_ids = set(type_subs + action_subs)
            
            for sub_id in all_sub_ids:
                subscription = self._subscriptions.get(sub_id)
                if subscription and subscription.is_active:
                    # Check if subscription matches
                    type_match = (not subscription.message_types or 
                                message.message_type in subscription.message_types)
                    action_match = (not subscription.actions or 
                                  message.action in subscription.actions)
                    
                    if type_match and action_match:
                        matching_subscriptions.append(subscription)
        
        # Sort by priority
        matching_subscriptions.sort(key=lambda s: s.priority, reverse=True)
        return matching_subscriptions
    
    def get_subscription_stats(self) -> Dict[str, Any]:
        """Get subscription statistics."""
        with self._lock:
            active_count = sum(1 for s in self._subscriptions.values() if s.is_active)
            total_messages = sum(s.message_count for s in self._subscriptions.values())
            total_errors = sum(s.error_count for s in self._subscriptions.values())
            
            return {
                'total_subscriptions': len(self._subscriptions),
                'active_subscriptions': active_count,
                'total_messages_processed': total_messages,
                'total_errors': total_errors,
                'type_indexes': len(self._type_subscriptions),
                'action_indexes': len(self._action_subscriptions)
            }


class MessageRouter:
    """Routes messages to appropriate handlers."""
    
    def __init__(self, subscription_manager: SubscriptionManager,
                 config: Optional[DispatcherConfig] = None):
        """Initialize message router."""
        self._subscription_manager = subscription_manager
        self._config = config or DispatcherConfig()
        self._circuit_breaker_states: Dict[str, Dict[str, Any]] = {}
        self._rate_limiter: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.RLock()
    
    async def route_message(self, message: Message) -> DispatchResult:
        """Route a message to matching handlers."""
        start_time = time.time()
        result = DispatchResult(
            message_id=message.message_id,
            success=False
        )
        
        try:
            # Get matching subscriptions
            subscriptions = self._subscription_manager.get_matching_subscriptions(message)
            
            if not subscriptions:
                result.success = True  # No handlers is not an error
                return result
            
            # Route to handlers
            tasks = []
            for subscription in subscriptions:
                if self._should_route_to_handler(subscription):
                    task = self._route_to_handler(message, subscription)
                    tasks.append(task)
            
            # Wait for all handlers
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, task_result in enumerate(results):
                    subscription = subscriptions[i]
                    if isinstance(task_result, Exception):
                        result.failed_count += 1
                        result.errors.append(f"Handler {subscription.subscription_id}: {str(task_result)}")
                        self._update_circuit_breaker(subscription.subscription_id, False)
                    elif task_result:
                        result.delivered_count += 1
                        result.handlers_called.append(subscription.subscription_id)
                        self._update_circuit_breaker(subscription.subscription_id, True)
                    else:
                        result.failed_count += 1
                        result.errors.append(f"Handler {subscription.subscription_id}: returned False")
                        self._update_circuit_breaker(subscription.subscription_id, False)
            
            result.success = result.delivered_count > 0 or len(subscriptions) == 0
            
        except Exception as e:
            result.errors.append(f"Routing error: {str(e)}")
        
        finally:
            result.processing_time_ms = (time.time() - start_time) * 1000
        
        return result
    
    async def _route_to_handler(self, message: Message, subscription: Subscription) -> bool:
        """Route message to a specific handler."""
        try:
            # Check rate limiting
            if self._config.enable_rate_limiting:
                if not self._check_rate_limit(subscription.subscription_id):
                    return False
            
            # Update subscription stats
            subscription.last_used_timestamp = datetime.now()
            subscription.message_count += 1
            
            # Call handler
            if subscription.handler.can_handle(message):
                success = await asyncio.wait_for(
                    subscription.handler.handle_message(message),
                    timeout=self._config.handler_timeout_seconds
                )
                return success
            
            return False
            
        except asyncio.TimeoutError:
            subscription.error_count += 1
            raise Exception(f"Handler timeout after {self._config.handler_timeout_seconds}s")
        except Exception as e:
            subscription.error_count += 1
            raise e
    
    def _should_route_to_handler(self, subscription: Subscription) -> bool:
        """Check if message should be routed to handler."""
        if not subscription.is_active:
            return False
        
        # Check circuit breaker
        if self._config.enable_circuit_breaker:
            return self._is_circuit_closed(subscription.subscription_id)
        
        return True
    
    def _check_rate_limit(self, subscription_id: str) -> bool:
        """Check rate limiting for subscription."""
        if not self._config.enable_rate_limiting:
            return True
        
        current_time = time.time()
        window_start = current_time - 1.0  # 1 second window
        
        with self._lock:
            # Clean old entries
            self._rate_limiter[subscription_id] = [
                t for t in self._rate_limiter[subscription_id] if t > window_start
            ]
            
            # Check limit
            if len(self._rate_limiter[subscription_id]) >= self._config.rate_limit_per_second:
                return False
            
            # Add current request
            self._rate_limiter[subscription_id].append(current_time)
            return True
    
    def _is_circuit_closed(self, subscription_id: str) -> bool:
        """Check if circuit breaker is closed (allowing requests)."""
        if subscription_id not in self._circuit_breaker_states:
            self._circuit_breaker_states[subscription_id] = {
                'state': 'closed',
                'failure_count': 0,
                'last_failure_time': None,
                'next_attempt_time': None
            }
        
        state = self._circuit_breaker_states[subscription_id]
        current_time = time.time()
        
        if state['state'] == 'closed':
            return True
        elif state['state'] == 'open':
            # Check if we should try again
            if current_time >= state['next_attempt_time']:
                state['state'] = 'half_open'
                return True
            return False
        elif state['state'] == 'half_open':
            return True
        
        return False
    
    def _update_circuit_breaker(self, subscription_id: str, success: bool) -> None:
        """Update circuit breaker state."""
        if not self._config.enable_circuit_breaker:
            return
        
        if subscription_id not in self._circuit_breaker_states:
            return
        
        state = self._circuit_breaker_states[subscription_id]
        current_time = time.time()
        
        if success:
            if state['state'] == 'half_open':
                state['state'] = 'closed'
            state['failure_count'] = 0
        else:
            state['failure_count'] += 1
            state['last_failure_time'] = current_time
            
            if state['failure_count'] >= self._config.circuit_breaker_threshold:
                state['state'] = 'open'
                state['next_attempt_time'] = current_time + 60  # 1 minute timeout


class MessageDispatcher(IMessageDispatcher):
    """
    Production-ready message dispatcher for publish-subscribe communication.

    Routes messages between application components using publish-subscribe pattern
    for loose coupling with delivery guarantees and error handling.
    """

    def __init__(self,
                 config: Optional[DispatcherConfig] = None,
                 app_state_manager: Optional[AppStateManager] = None):
        """Initialize the message dispatcher."""
        self._config = config or DispatcherConfig()
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("message_dispatcher")
        self._validation_engine = ValidationEngine()

        # Core components
        self._subscription_manager = SubscriptionManager()
        self._message_router = MessageRouter(self._subscription_manager, self._config)
        self._delivery_guarantee = DeliveryGuarantee(self._config)

        # Message queue
        self._message_queue: List[QueuedMessage] = []
        self._queue_lock = threading.RLock()

        # Processing control
        self._is_running = False
        self._processing_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

        # Metrics
        self._metrics = {
            'messages_dispatched': 0,
            'messages_failed': 0,
            'handlers_called': 0,
            'average_processing_time_ms': 0.0,
            'queue_size': 0,
            'active_subscriptions': 0
        }
        self._metrics_lock = threading.RLock()

    async def initialize(self) -> bool:
        """Initialize the message dispatcher."""
        try:
            self._logger.info("Initializing message dispatcher...")

            # Start processing loop
            self._is_running = True
            self._processing_task = asyncio.create_task(self._processing_loop())

            self._logger.info("Message dispatcher initialized successfully")
            return True

        except Exception as e:
            self._logger.error(f"Error initializing message dispatcher: {e}")
            return False

    async def shutdown(self) -> bool:
        """Shutdown the message dispatcher."""
        try:
            self._logger.info("Shutting down message dispatcher...")

            self._is_running = False
            self._shutdown_event.set()

            if self._processing_task:
                await self._processing_task

            # Process remaining messages
            await self._process_remaining_messages()

            self._logger.info("Message dispatcher shutdown complete")
            return True

        except Exception as e:
            self._logger.error(f"Error shutting down message dispatcher: {e}")
            return False

    async def dispatch_message(self, message: Message) -> DispatchResult:
        """
        Dispatch a message to registered handlers.

        Args:
            message: Message to dispatch

        Returns:
            DispatchResult with dispatch details
        """
        try:
            # Validate message
            if not self._validate_message(message):
                return DispatchResult(
                    message_id=message.message_id,
                    success=False,
                    errors=["Invalid message format"]
                )

            # Set message status
            message.status = MessageStatus.PROCESSING

            # Track for delivery guarantee
            if message.delivery_mode != DeliveryMode.FIRE_AND_FORGET:
                self._delivery_guarantee.track_message(message)

            # Add to queue if using priority queue
            if self._config.enable_priority_queue:
                await self._enqueue_message(message)
                return DispatchResult(
                    message_id=message.message_id,
                    success=True,
                    metadata={'queued': True}
                )
            else:
                # Direct dispatch
                return await self._dispatch_message_direct(message)

        except Exception as e:
            self._logger.error(f"Error dispatching message {message.message_id}: {e}")
            return DispatchResult(
                message_id=message.message_id,
                success=False,
                errors=[str(e)]
            )

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
        try:
            subscription_id = self._subscription_manager.add_subscription(
                handler=handler,
                message_types=message_types,
                actions=actions
            )

            self._update_metrics()
            self._logger.debug(f"Added subscription {subscription_id}")

            return subscription_id

        except Exception as e:
            self._logger.error(f"Error adding subscription: {e}")
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
            success = self._subscription_manager.remove_subscription(subscription_id)

            if success:
                self._update_metrics()
                self._logger.debug(f"Removed subscription {subscription_id}")

            return success

        except Exception as e:
            self._logger.error(f"Error removing subscription {subscription_id}: {e}")
            return False

    async def _processing_loop(self) -> None:
        """Main processing loop for queued messages."""
        self._logger.info("Starting message processing loop")

        while self._is_running:
            try:
                # Process queued messages
                await self._process_queue_batch()

                # Process retry messages
                await self._process_retry_messages()

                # Small delay to prevent busy waiting
                await asyncio.sleep(0.01)

            except Exception as e:
                self._logger.error(f"Error in processing loop: {e}")
                await asyncio.sleep(1.0)  # Longer delay on error

        self._logger.info("Message processing loop stopped")

    async def _enqueue_message(self, message: Message) -> None:
        """Add message to priority queue."""
        priority = message.priority.value
        timestamp = time.time()

        queued_message = QueuedMessage(
            priority=priority,
            timestamp=timestamp,
            message=message
        )

        with self._queue_lock:
            heapq.heappush(self._message_queue, queued_message)

            # Check queue size limit
            if len(self._message_queue) > self._config.queue_size_limit:
                # Remove lowest priority message
                self._message_queue.sort(key=lambda x: (x.priority, x.timestamp))
                removed = self._message_queue.pop(0)
                heapq.heapify(self._message_queue)

                self._logger.warning(f"Queue full, dropped message {removed.message.message_id}")

        self._update_metrics()

    async def _process_queue_batch(self) -> None:
        """Process a batch of queued messages."""
        batch_size = min(self._config.max_concurrent_dispatches, len(self._message_queue))

        if batch_size == 0:
            return

        # Get batch of messages
        batch = []
        with self._queue_lock:
            for _ in range(batch_size):
                if self._message_queue:
                    batch.append(heapq.heappop(self._message_queue))

        if not batch:
            return

        # Process batch concurrently
        tasks = [self._dispatch_message_direct(queued_msg.message) for queued_msg in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Update metrics
        for result in results:
            if isinstance(result, DispatchResult):
                self._update_dispatch_metrics(result)

    async def _dispatch_message_direct(self, message: Message) -> DispatchResult:
        """Dispatch message directly to handlers."""
        try:
            # Route message
            result = await self._message_router.route_message(message)

            # Update delivery guarantee
            if message.delivery_mode != DeliveryMode.FIRE_AND_FORGET:
                if result.success and result.delivered_count > 0:
                    self._delivery_guarantee.mark_delivered(message.message_id)
                else:
                    self._delivery_guarantee.mark_failed(message.message_id)

            # Update message status
            message.status = MessageStatus.DELIVERED if result.success else MessageStatus.FAILED

            return result

        except Exception as e:
            self._logger.error(f"Error in direct dispatch: {e}")
            message.status = MessageStatus.FAILED
            return DispatchResult(
                message_id=message.message_id,
                success=False,
                errors=[str(e)]
            )

    async def _process_retry_messages(self) -> None:
        """Process messages that need retry."""
        retry_messages = self._delivery_guarantee.get_retry_messages()

        for message in retry_messages:
            if message.retry_count < message.max_retries:
                message.retry_count += 1
                await self._dispatch_message_direct(message)

    async def _process_remaining_messages(self) -> None:
        """Process remaining messages during shutdown."""
        self._logger.info("Processing remaining messages...")

        # Process all queued messages
        while self._message_queue:
            await self._process_queue_batch()

        # Process final retry messages
        await self._process_retry_messages()

    def _validate_message(self, message: Message) -> bool:
        """Validate message format and content."""
        try:
            # Basic validation
            if not message.message_id:
                return False

            if not isinstance(message.message_type, MessageType):
                return False

            if not isinstance(message.priority, MessagePriority):
                return False

            # Use validation engine for detailed validation
            return self._validation_engine.validate_object(message)

        except Exception as e:
            self._logger.error(f"Message validation error: {e}")
            return False

    def _update_metrics(self) -> None:
        """Update dispatcher metrics."""
        with self._metrics_lock:
            with self._queue_lock:
                self._metrics['queue_size'] = len(self._message_queue)

            stats = self._subscription_manager.get_subscription_stats()
            self._metrics['active_subscriptions'] = stats['active_subscriptions']

    def _update_dispatch_metrics(self, result: DispatchResult) -> None:
        """Update dispatch-specific metrics."""
        with self._metrics_lock:
            self._metrics['messages_dispatched'] += 1
            self._metrics['handlers_called'] += result.delivered_count

            if not result.success:
                self._metrics['messages_failed'] += 1

            # Update average processing time
            current_avg = self._metrics['average_processing_time_ms']
            total_messages = self._metrics['messages_dispatched']

            self._metrics['average_processing_time_ms'] = (
                (current_avg * (total_messages - 1) + result.processing_time_ms) / total_messages
            )

    def get_metrics(self) -> Dict[str, Any]:
        """Get dispatcher metrics."""
        with self._metrics_lock:
            return self._metrics.copy()

    def get_subscription_stats(self) -> Dict[str, Any]:
        """Get subscription statistics."""
        return self._subscription_manager.get_subscription_stats()

    def get_dead_letter_messages(self) -> List[Message]:
        """Get messages in dead letter queue."""
        return self._delivery_guarantee.get_dead_letter_messages()
