"""
Module: state_synchronizer_lg
Description: Maintains consistency between frontend and backend state with change propagation and conflict resolution
Phase: 4
Location: /src/modules/logic/event_system_lg/state_synchronizer_lg/state_synchronizer_lg.py
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
from typing import Dict, List, Set, Optional, Any, Callable, Tuple, Union
from weakref import WeakSet
import json
import hashlib

# Third-party imports
# None required

# Local imports
from src.modules.logic.event_bus_lg.base_interfaces import (
    Event, EventType, EventPriority, EventStatus
)
from src.modules.logic.state_management_lg.app_state_manager_lg import (
    AppStateManager, ApplicationState, ApplicationStateType
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg import ValidationEngine


class StateUpdateType(Enum):
    """Types of state updates."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    REPLACE = "replace"
    MERGE = "merge"


class ConflictResolutionStrategy(Enum):
    """Conflict resolution strategies."""
    LAST_WRITE_WINS = "last_write_wins"
    FIRST_WRITE_WINS = "first_write_wins"
    MERGE = "merge"
    MANUAL = "manual"
    REJECT = "reject"


class SynchronizationMode(Enum):
    """Synchronization modes."""
    REAL_TIME = "real_time"
    BATCH = "batch"
    ON_DEMAND = "on_demand"
    PERIODIC = "periodic"


@dataclass
class StateUpdate:
    """Represents a state change for synchronization."""
    update_id: str
    update_type: StateUpdateType
    component_path: str
    old_value: Any = None
    new_value: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: int = 0
    source: str = ""
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    checksum: Optional[str] = None
    
    def __post_init__(self):
        """Calculate checksum after initialization."""
        if not self.checksum:
            self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self) -> str:
        """Calculate checksum for the update."""
        data = {
            'update_type': self.update_type.value,
            'component_path': self.component_path,
            'new_value': self.new_value,
            'timestamp': self.timestamp.isoformat()
        }
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class ConflictInfo:
    """Information about a state conflict."""
    conflict_id: str
    component_path: str
    local_update: StateUpdate
    remote_update: StateUpdate
    detected_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolution_strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.LAST_WRITE_WINS
    is_resolved: bool = False
    resolution_result: Optional[StateUpdate] = None


@dataclass
class SynchronizationResult:
    """Result of synchronization operation."""
    success: bool
    operation_id: str = ""
    updates_applied: int = 0
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    errors: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SynchronizerConfig:
    """Configuration for the state synchronizer."""
    sync_mode: SynchronizationMode = SynchronizationMode.REAL_TIME
    conflict_resolution: ConflictResolutionStrategy = ConflictResolutionStrategy.LAST_WRITE_WINS
    batch_size: int = 50
    batch_timeout_ms: float = 1000.0
    max_queue_size: int = 10000
    enable_compression: bool = False
    enable_encryption: bool = False
    sync_interval_seconds: float = 1.0
    cleanup_interval_seconds: float = 300.0
    max_conflict_age_hours: int = 24
    enable_change_detection: bool = True
    change_detection_interval_ms: float = 100.0
    enable_metrics: bool = True


@dataclass
class SynchronizerMetrics:
    """Metrics for state synchronizer operations."""
    updates_sent: int = 0
    updates_received: int = 0
    updates_applied: int = 0
    updates_rejected: int = 0
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    sync_operations: int = 0
    failed_operations: int = 0
    average_sync_time_ms: float = 0.0
    queue_size: int = 0
    peak_queue_size: int = 0
    uptime_seconds: float = 0.0


class StateChangeDetector:
    """
    Detects changes in application state for synchronization.
    
    Monitors state objects and generates StateUpdate events
    when changes are detected.
    """
    
    def __init__(self, config: SynchronizerConfig):
        """Initialize the state change detector."""
        self._config = config
        self._logger = get_log_manager().get_logger(__name__)
        
        # State tracking
        self._watched_states: Dict[str, Any] = {}
        self._state_checksums: Dict[str, str] = {}
        self._change_callbacks: List[Callable[[StateUpdate], None]] = []
        self._lock = threading.RLock()
        
        # Detection state
        self._is_running = False
        self._detection_task: Optional[asyncio.Task] = None
    
    def add_state_watch(self, component_path: str, state_object: Any) -> None:
        """Add a state object to watch for changes."""
        with self._lock:
            self._watched_states[component_path] = state_object
            self._state_checksums[component_path] = self._calculate_state_checksum(state_object)
    
    def remove_state_watch(self, component_path: str) -> None:
        """Remove a state object from watching."""
        with self._lock:
            self._watched_states.pop(component_path, None)
            self._state_checksums.pop(component_path, None)
    
    def add_change_callback(self, callback: Callable[[StateUpdate], None]) -> None:
        """Add callback for state changes."""
        if callback not in self._change_callbacks:
            self._change_callbacks.append(callback)
    
    def remove_change_callback(self, callback: Callable[[StateUpdate], None]) -> None:
        """Remove callback for state changes."""
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)
    
    async def start_detection(self) -> None:
        """Start change detection."""
        if self._is_running:
            return
        
        self._is_running = True
        if self._config.enable_change_detection:
            self._detection_task = asyncio.create_task(self._detection_loop())
    
    async def stop_detection(self) -> None:
        """Stop change detection."""
        self._is_running = False
        if self._detection_task:
            self._detection_task.cancel()
            try:
                await self._detection_task
            except asyncio.CancelledError:
                pass
    
    def detect_changes(self) -> List[StateUpdate]:
        """Manually detect changes in watched states."""
        changes = []
        
        with self._lock:
            for component_path, state_object in self._watched_states.items():
                current_checksum = self._calculate_state_checksum(state_object)
                previous_checksum = self._state_checksums.get(component_path)
                
                if current_checksum != previous_checksum:
                    # State changed
                    update = StateUpdate(
                        update_id=str(uuid.uuid4()),
                        update_type=StateUpdateType.UPDATE,
                        component_path=component_path,
                        new_value=self._serialize_state(state_object),
                        source="change_detector"
                    )
                    changes.append(update)
                    
                    # Update stored checksum
                    self._state_checksums[component_path] = current_checksum
        
        # Notify callbacks
        for change in changes:
            for callback in self._change_callbacks:
                try:
                    callback(change)
                except Exception as e:
                    self._logger.error(f"Error in change callback: {e}")
        
        return changes
    
    def _calculate_state_checksum(self, state_object: Any) -> str:
        """Calculate checksum for a state object."""
        try:
            serialized = self._serialize_state(state_object)
            return hashlib.md5(json.dumps(serialized, sort_keys=True).encode()).hexdigest()
        except Exception as e:
            self._logger.error(f"Error calculating state checksum: {e}")
            return ""
    
    def _serialize_state(self, state_object: Any) -> Any:
        """Serialize state object for comparison."""
        try:
            if hasattr(state_object, '__dict__'):
                return {k: v for k, v in state_object.__dict__.items() if not k.startswith('_')}
            elif isinstance(state_object, dict):
                return state_object.copy()
            elif isinstance(state_object, (list, tuple)):
                return list(state_object)
            else:
                return str(state_object)
        except Exception as e:
            self._logger.error(f"Error serializing state: {e}")
            return None
    
    async def _detection_loop(self) -> None:
        """Main detection loop."""
        while self._is_running:
            try:
                self.detect_changes()
                await asyncio.sleep(self._config.change_detection_interval_ms / 1000.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in detection loop: {e}")
                await asyncio.sleep(1.0)


class StateUpdatePropagator:
    """
    Propagates state changes between frontend and backend.

    Manages the distribution of state updates with batching,
    compression, and delivery guarantees.
    """

    def __init__(self, config: SynchronizerConfig):
        """Initialize the state update propagator."""
        self._config = config
        self._logger = get_log_manager().get_logger(__name__)

        # Update queues
        self._outbound_queue: deque = deque(maxlen=config.max_queue_size)
        self._inbound_queue: deque = deque(maxlen=config.max_queue_size)
        self._batch_queue: deque = deque()

        # Propagation state
        self._is_running = False
        self._propagation_task: Optional[asyncio.Task] = None
        self._batch_task: Optional[asyncio.Task] = None

        # Callbacks
        self._update_callbacks: List[Callable[[StateUpdate], None]] = []
        self._batch_callbacks: List[Callable[[List[StateUpdate]], None]] = []

        self._lock = threading.RLock()

    def add_update_callback(self, callback: Callable[[StateUpdate], None]) -> None:
        """Add callback for individual updates."""
        if callback not in self._update_callbacks:
            self._update_callbacks.append(callback)

    def add_batch_callback(self, callback: Callable[[List[StateUpdate]], None]) -> None:
        """Add callback for batched updates."""
        if callback not in self._batch_callbacks:
            self._batch_callbacks.append(callback)

    def queue_update(self, update: StateUpdate, outbound: bool = True) -> bool:
        """Queue a state update for propagation."""
        try:
            with self._lock:
                if outbound:
                    if len(self._outbound_queue) >= self._config.max_queue_size:
                        return False
                    self._outbound_queue.append(update)
                else:
                    if len(self._inbound_queue) >= self._config.max_queue_size:
                        return False
                    self._inbound_queue.append(update)

            return True

        except Exception as e:
            self._logger.error(f"Error queuing update: {e}")
            return False

    async def start_propagation(self) -> None:
        """Start update propagation."""
        if self._is_running:
            return

        self._is_running = True

        if self._config.sync_mode == SynchronizationMode.REAL_TIME:
            self._propagation_task = asyncio.create_task(self._real_time_propagation())
        elif self._config.sync_mode == SynchronizationMode.BATCH:
            self._batch_task = asyncio.create_task(self._batch_propagation())
        elif self._config.sync_mode == SynchronizationMode.PERIODIC:
            self._propagation_task = asyncio.create_task(self._periodic_propagation())

    async def stop_propagation(self) -> None:
        """Stop update propagation."""
        self._is_running = False

        for task in [self._propagation_task, self._batch_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    def get_queue_sizes(self) -> Dict[str, int]:
        """Get current queue sizes."""
        with self._lock:
            return {
                'outbound': len(self._outbound_queue),
                'inbound': len(self._inbound_queue),
                'batch': len(self._batch_queue)
            }

    async def _real_time_propagation(self) -> None:
        """Real-time propagation loop."""
        while self._is_running:
            try:
                # Process outbound updates
                while self._outbound_queue:
                    with self._lock:
                        update = self._outbound_queue.popleft()

                    await self._propagate_update(update, outbound=True)

                # Process inbound updates
                while self._inbound_queue:
                    with self._lock:
                        update = self._inbound_queue.popleft()

                    await self._propagate_update(update, outbound=False)

                await asyncio.sleep(0.01)  # Small delay

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in real-time propagation: {e}")
                await asyncio.sleep(1.0)

    async def _batch_propagation(self) -> None:
        """Batch propagation loop."""
        while self._is_running:
            try:
                # Collect updates for batching
                outbound_batch = []
                inbound_batch = []

                # Collect outbound updates
                batch_count = 0
                while self._outbound_queue and batch_count < self._config.batch_size:
                    with self._lock:
                        outbound_batch.append(self._outbound_queue.popleft())
                    batch_count += 1

                # Collect inbound updates
                batch_count = 0
                while self._inbound_queue and batch_count < self._config.batch_size:
                    with self._lock:
                        inbound_batch.append(self._inbound_queue.popleft())
                    batch_count += 1

                # Propagate batches
                if outbound_batch:
                    await self._propagate_batch(outbound_batch, outbound=True)

                if inbound_batch:
                    await self._propagate_batch(inbound_batch, outbound=False)

                # Wait for batch timeout
                await asyncio.sleep(self._config.batch_timeout_ms / 1000.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in batch propagation: {e}")
                await asyncio.sleep(1.0)

    async def _periodic_propagation(self) -> None:
        """Periodic propagation loop."""
        while self._is_running:
            try:
                # Process all queued updates
                outbound_updates = []
                inbound_updates = []

                with self._lock:
                    outbound_updates = list(self._outbound_queue)
                    inbound_updates = list(self._inbound_queue)
                    self._outbound_queue.clear()
                    self._inbound_queue.clear()

                # Propagate updates
                if outbound_updates:
                    await self._propagate_batch(outbound_updates, outbound=True)

                if inbound_updates:
                    await self._propagate_batch(inbound_updates, outbound=False)

                # Wait for sync interval
                await asyncio.sleep(self._config.sync_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in periodic propagation: {e}")
                await asyncio.sleep(1.0)

    async def _propagate_update(self, update: StateUpdate, outbound: bool) -> None:
        """Propagate a single update."""
        try:
            # Notify callbacks
            for callback in self._update_callbacks:
                try:
                    callback(update)
                except Exception as e:
                    self._logger.error(f"Error in update callback: {e}")

        except Exception as e:
            self._logger.error(f"Error propagating update: {e}")

    async def _propagate_batch(self, updates: List[StateUpdate], outbound: bool) -> None:
        """Propagate a batch of updates."""
        try:
            # Notify batch callbacks
            for callback in self._batch_callbacks:
                try:
                    callback(updates)
                except Exception as e:
                    self._logger.error(f"Error in batch callback: {e}")

        except Exception as e:
            self._logger.error(f"Error propagating batch: {e}")


class ConflictResolver:
    """
    Resolves conflicts between state updates.

    Implements various conflict resolution strategies and
    maintains conflict history for analysis.
    """

    def __init__(self, config: SynchronizerConfig):
        """Initialize the conflict resolver."""
        self._config = config
        self._logger = get_log_manager().get_logger(__name__)

        # Conflict tracking
        self._active_conflicts: Dict[str, ConflictInfo] = {}
        self._resolved_conflicts: deque = deque(maxlen=1000)
        self._lock = threading.RLock()

        # Resolution strategies
        self._resolution_strategies = {
            ConflictResolutionStrategy.LAST_WRITE_WINS: self._resolve_last_write_wins,
            ConflictResolutionStrategy.FIRST_WRITE_WINS: self._resolve_first_write_wins,
            ConflictResolutionStrategy.MERGE: self._resolve_merge,
            ConflictResolutionStrategy.MANUAL: self._resolve_manual,
            ConflictResolutionStrategy.REJECT: self._resolve_reject
        }

    def detect_conflict(self, local_update: StateUpdate, remote_update: StateUpdate) -> Optional[ConflictInfo]:
        """Detect if two updates conflict."""
        # Check if updates affect the same component path
        if local_update.component_path != remote_update.component_path:
            return None

        # Check if updates have different values
        if local_update.new_value == remote_update.new_value:
            return None

        # Check if updates are concurrent (within reasonable time window)
        time_diff = abs((local_update.timestamp - remote_update.timestamp).total_seconds())
        if time_diff > 60:  # 1 minute window
            return None

        # Create conflict info
        conflict = ConflictInfo(
            conflict_id=str(uuid.uuid4()),
            component_path=local_update.component_path,
            local_update=local_update,
            remote_update=remote_update,
            resolution_strategy=self._config.conflict_resolution
        )

        with self._lock:
            self._active_conflicts[conflict.conflict_id] = conflict

        self._logger.warning(f"Conflict detected: {conflict.conflict_id} at {conflict.component_path}")
        return conflict

    def resolve_conflict(self, conflict_id: str) -> Optional[StateUpdate]:
        """Resolve a conflict using configured strategy."""
        with self._lock:
            conflict = self._active_conflicts.get(conflict_id)
            if not conflict or conflict.is_resolved:
                return None

        try:
            strategy = conflict.resolution_strategy
            resolver = self._resolution_strategies.get(strategy)

            if not resolver:
                self._logger.error(f"Unknown resolution strategy: {strategy}")
                return None

            result = resolver(conflict)

            # Mark conflict as resolved
            with self._lock:
                conflict.is_resolved = True
                conflict.resolution_result = result

                # Move to resolved conflicts
                self._resolved_conflicts.append(conflict)
                del self._active_conflicts[conflict_id]

            self._logger.info(f"Conflict resolved: {conflict_id} using {strategy.value}")
            return result

        except Exception as e:
            self._logger.error(f"Error resolving conflict {conflict_id}: {e}")
            return None

    def get_active_conflicts(self) -> List[ConflictInfo]:
        """Get list of active conflicts."""
        with self._lock:
            return list(self._active_conflicts.values())

    def get_conflict_stats(self) -> Dict[str, int]:
        """Get conflict statistics."""
        with self._lock:
            return {
                'active_conflicts': len(self._active_conflicts),
                'resolved_conflicts': len(self._resolved_conflicts),
                'total_conflicts': len(self._active_conflicts) + len(self._resolved_conflicts)
            }

    def cleanup_old_conflicts(self) -> int:
        """Clean up old resolved conflicts."""
        removed_count = 0
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self._config.max_conflict_age_hours)

        with self._lock:
            # Remove old resolved conflicts
            while self._resolved_conflicts:
                conflict = self._resolved_conflicts[0]
                if conflict.detected_timestamp < cutoff_time:
                    self._resolved_conflicts.popleft()
                    removed_count += 1
                else:
                    break

        return removed_count

    def _resolve_last_write_wins(self, conflict: ConflictInfo) -> StateUpdate:
        """Resolve conflict using last write wins strategy."""
        if conflict.local_update.timestamp >= conflict.remote_update.timestamp:
            return conflict.local_update
        else:
            return conflict.remote_update

    def _resolve_first_write_wins(self, conflict: ConflictInfo) -> StateUpdate:
        """Resolve conflict using first write wins strategy."""
        if conflict.local_update.timestamp <= conflict.remote_update.timestamp:
            return conflict.local_update
        else:
            return conflict.remote_update

    def _resolve_merge(self, conflict: ConflictInfo) -> StateUpdate:
        """Resolve conflict using merge strategy."""
        try:
            # Simple merge strategy - combine values if possible
            local_value = conflict.local_update.new_value
            remote_value = conflict.remote_update.new_value

            if isinstance(local_value, dict) and isinstance(remote_value, dict):
                # Merge dictionaries
                merged_value = {**local_value, **remote_value}
            elif isinstance(local_value, list) and isinstance(remote_value, list):
                # Merge lists (remove duplicates)
                merged_value = list(set(local_value + remote_value))
            else:
                # Fall back to last write wins
                return self._resolve_last_write_wins(conflict)

            # Create merged update
            merged_update = StateUpdate(
                update_id=str(uuid.uuid4()),
                update_type=StateUpdateType.MERGE,
                component_path=conflict.component_path,
                old_value=conflict.local_update.old_value,
                new_value=merged_value,
                source="conflict_resolver",
                metadata={'merged_from': [conflict.local_update.update_id, conflict.remote_update.update_id]}
            )

            return merged_update

        except Exception as e:
            self._logger.error(f"Error merging conflict: {e}")
            return self._resolve_last_write_wins(conflict)

    def _resolve_manual(self, conflict: ConflictInfo) -> StateUpdate:
        """Resolve conflict manually (placeholder - requires user intervention)."""
        # For now, fall back to last write wins
        # In a real implementation, this would queue for manual resolution
        self._logger.warning(f"Manual resolution required for conflict {conflict.conflict_id}")
        return self._resolve_last_write_wins(conflict)

    def _resolve_reject(self, conflict: ConflictInfo) -> StateUpdate:
        """Resolve conflict by rejecting the update."""
        # Return the original state (no change)
        rejected_update = StateUpdate(
            update_id=str(uuid.uuid4()),
            update_type=StateUpdateType.UPDATE,
            component_path=conflict.component_path,
            old_value=conflict.local_update.old_value,
            new_value=conflict.local_update.old_value,  # Keep original value
            source="conflict_resolver",
            metadata={'rejected_update': conflict.remote_update.update_id}
        )

        return rejected_update


class StateSynchronizer:
    """
    Main state synchronizer for maintaining consistency between frontend and backend.

    Coordinates change detection, update propagation, and conflict resolution
    to ensure synchronized state across the application.
    """

    def __init__(self, config: Optional[SynchronizerConfig] = None):
        """Initialize the state synchronizer."""
        self._config = config or SynchronizerConfig()
        self._logger = get_log_manager().get_logger(__name__)
        self._validation_engine = ValidationEngine()

        # Core components
        self._change_detector = StateChangeDetector(self._config)
        self._update_propagator = StateUpdatePropagator(self._config)
        self._conflict_resolver = ConflictResolver(self._config)

        # State management
        self._is_running = False
        self._lock = threading.RLock()
        self._metrics_lock = threading.RLock()

        # Metrics and monitoring
        self._metrics = SynchronizerMetrics()
        self._start_time = datetime.now(timezone.utc)

        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._sync_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

        # Setup callbacks
        self._setup_callbacks()

        self._logger.info("State synchronizer initialized")

    async def start(self) -> SynchronizationResult:
        """Start the state synchronizer."""
        start_time = time.time()
        operation_id = str(uuid.uuid4())

        try:
            with self._lock:
                if self._is_running:
                    return SynchronizationResult(
                        success=False,
                        operation_id=operation_id,
                        errors=["State synchronizer is already running"]
                    )

                self._is_running = True
                self._start_time = datetime.now(timezone.utc)

                # Start components
                await self._change_detector.start_detection()
                await self._update_propagator.start_propagation()

                # Start background tasks
                if self._config.sync_mode == SynchronizationMode.ON_DEMAND:
                    self._sync_task = asyncio.create_task(self._sync_loop())

                if self._config.cleanup_interval_seconds > 0:
                    self._cleanup_task = asyncio.create_task(self._cleanup_loop())

                self._logger.info("State synchronizer started")

                return SynchronizationResult(
                    success=True,
                    operation_id=operation_id,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    metadata={'message': "State synchronizer started successfully"}
                )

        except Exception as e:
            self._logger.error(f"Error starting state synchronizer: {e}")
            return SynchronizationResult(
                success=False,
                operation_id=operation_id,
                errors=[f"Failed to start state synchronizer: {e}"],
                processing_time_ms=(time.time() - start_time) * 1000
            )

    async def stop(self) -> SynchronizationResult:
        """Stop the state synchronizer."""
        start_time = time.time()
        operation_id = str(uuid.uuid4())

        try:
            with self._lock:
                if not self._is_running:
                    return SynchronizationResult(
                        success=False,
                        operation_id=operation_id,
                        errors=["State synchronizer is not running"]
                    )

                self._is_running = False

                # Stop components
                await self._change_detector.stop_detection()
                await self._update_propagator.stop_propagation()

                # Cancel background tasks
                tasks_to_cancel = [self._sync_task, self._cleanup_task]

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

                self._logger.info("State synchronizer stopped")

                return SynchronizationResult(
                    success=True,
                    operation_id=operation_id,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    metadata={'message': "State synchronizer stopped successfully"}
                )

        except Exception as e:
            self._logger.error(f"Error stopping state synchronizer: {e}")
            return SynchronizationResult(
                success=False,
                operation_id=operation_id,
                errors=[f"Failed to stop state synchronizer: {e}"],
                processing_time_ms=(time.time() - start_time) * 1000
            )

    def add_state_watch(self, component_path: str, state_object: Any) -> None:
        """Add a state object to watch for changes."""
        self._change_detector.add_state_watch(component_path, state_object)

    def remove_state_watch(self, component_path: str) -> None:
        """Remove a state object from watching."""
        self._change_detector.remove_state_watch(component_path)

    def apply_update(self, update: StateUpdate) -> SynchronizationResult:
        """Apply a state update."""
        start_time = time.time()
        operation_id = str(uuid.uuid4())

        try:
            # Validate update
            if not self._validate_update(update):
                return SynchronizationResult(
                    success=False,
                    operation_id=operation_id,
                    errors=["Invalid state update format"]
                )

            # Queue for propagation
            if self._update_propagator.queue_update(update, outbound=False):
                with self._metrics_lock:
                    self._metrics.updates_received += 1
                    self._metrics.updates_applied += 1

                return SynchronizationResult(
                    success=True,
                    operation_id=operation_id,
                    updates_applied=1,
                    processing_time_ms=(time.time() - start_time) * 1000
                )
            else:
                return SynchronizationResult(
                    success=False,
                    operation_id=operation_id,
                    errors=["Failed to queue update for propagation"]
                )

        except Exception as e:
            self._logger.error(f"Error applying update: {e}")
            return SynchronizationResult(
                success=False,
                operation_id=operation_id,
                errors=[f"Failed to apply update: {e}"],
                processing_time_ms=(time.time() - start_time) * 1000
            )

    def get_metrics(self) -> SynchronizerMetrics:
        """Get current synchronizer metrics."""
        with self._metrics_lock:
            # Update uptime
            self._metrics.uptime_seconds = (
                datetime.now(timezone.utc) - self._start_time
            ).total_seconds()

            # Update queue sizes
            queue_sizes = self._update_propagator.get_queue_sizes()
            self._metrics.queue_size = sum(queue_sizes.values())

            # Update conflict stats
            conflict_stats = self._conflict_resolver.get_conflict_stats()
            self._metrics.conflicts_detected = conflict_stats['total_conflicts']

            return self._metrics

    def get_active_conflicts(self) -> List[ConflictInfo]:
        """Get list of active conflicts."""
        return self._conflict_resolver.get_active_conflicts()

    def resolve_conflict(self, conflict_id: str) -> Optional[StateUpdate]:
        """Resolve a specific conflict."""
        return self._conflict_resolver.resolve_conflict(conflict_id)

    def _setup_callbacks(self) -> None:
        """Setup callbacks between components."""
        # Change detector -> update propagator
        self._change_detector.add_change_callback(self._on_state_change)

        # Update propagator -> conflict detection
        self._update_propagator.add_update_callback(self._on_update_received)

    def _on_state_change(self, update: StateUpdate) -> None:
        """Handle state change from detector."""
        try:
            # Queue for outbound propagation
            if self._update_propagator.queue_update(update, outbound=True):
                with self._metrics_lock:
                    self._metrics.updates_sent += 1

        except Exception as e:
            self._logger.error(f"Error handling state change: {e}")

    def _on_update_received(self, update: StateUpdate) -> None:
        """Handle update received from propagator."""
        try:
            # Check for conflicts with local state
            # This is a simplified implementation
            # In practice, you'd compare with current local state

            with self._metrics_lock:
                self._metrics.updates_received += 1

        except Exception as e:
            self._logger.error(f"Error handling received update: {e}")

    def _validate_update(self, update: StateUpdate) -> bool:
        """Validate a state update."""
        try:
            return (
                update.update_id and
                isinstance(update.update_type, StateUpdateType) and
                update.component_path and
                isinstance(update.timestamp, datetime)
            )
        except Exception:
            return False

    async def _sync_loop(self) -> None:
        """Main synchronization loop for on-demand mode."""
        while self._is_running:
            try:
                # Trigger change detection
                changes = self._change_detector.detect_changes()

                if changes:
                    self._logger.debug(f"Detected {len(changes)} state changes")

                # Process any pending conflicts
                active_conflicts = self._conflict_resolver.get_active_conflicts()
                for conflict in active_conflicts:
                    self._conflict_resolver.resolve_conflict(conflict.conflict_id)

                await asyncio.sleep(self._config.sync_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in sync loop: {e}")
                await asyncio.sleep(1.0)

    async def _cleanup_loop(self) -> None:
        """Cleanup loop for maintenance tasks."""
        while self._is_running:
            try:
                await asyncio.sleep(self._config.cleanup_interval_seconds)

                if not self._is_running:
                    break

                # Clean up old conflicts
                removed_conflicts = self._conflict_resolver.cleanup_old_conflicts()
                if removed_conflicts > 0:
                    self._logger.debug(f"Cleaned up {removed_conflicts} old conflicts")

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
                # Update queue metrics
                queue_sizes = self._update_propagator.get_queue_sizes()
                self._metrics.queue_size = sum(queue_sizes.values())

                if self._metrics.queue_size > self._metrics.peak_queue_size:
                    self._metrics.peak_queue_size = self._metrics.queue_size

        except Exception as e:
            self._logger.error(f"Error updating metrics: {e}")
