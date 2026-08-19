"""
Module: state_persistence_lg
Description: Handles state serialization, auto-save functionality, and state recovery from persistent storage
Phase: 1
Location: /src/modules/logic/state_management_lg/state_persistence_lg/state_persistence_lg.py
"""

# Standard library imports
import json
import pickle
import threading
import asyncio
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass, field
import logging
import gzip
import hashlib

# Local imports
from src.modules.logic.app_state_lg.app_state_lg import (
    AppState as ApplicationState
)
# Note: ApplicationStateType is not available in the simplified app_state_lg
# Using string literals for state types instead

# Optional database import - will be available when state_snapshots_db is implemented
try:
    from src.modules.database.app_state_db.state_snapshots_db.state_snapshots_db import StateSnapshotsDB
except ImportError:
    StateSnapshotsDB = None


class PersistenceMode(Enum):
    """Persistence operation modes."""
    MANUAL = "MANUAL"
    AUTO_SAVE = "AUTO_SAVE"
    CONTINUOUS = "CONTINUOUS"
    ON_CHANGE = "ON_CHANGE"


class SerializationFormat(Enum):
    """Serialization formats."""
    JSON = "JSON"
    PICKLE = "PICKLE"
    COMPRESSED_JSON = "COMPRESSED_JSON"
    COMPRESSED_PICKLE = "COMPRESSED_PICKLE"


class PersistenceStrategy(Enum):
    """Persistence strategies."""
    DATABASE_ONLY = "DATABASE_ONLY"
    FILE_ONLY = "FILE_ONLY"
    HYBRID = "HYBRID"
    MEMORY_CACHE = "MEMORY_CACHE"


@dataclass
class PersistenceConfiguration:
    """Configuration for state persistence."""
    mode: PersistenceMode = PersistenceMode.AUTO_SAVE
    format: SerializationFormat = SerializationFormat.JSON
    strategy: PersistenceStrategy = PersistenceStrategy.HYBRID
    auto_save_interval: float = 60.0  # seconds
    max_snapshots: int = 100
    compression_enabled: bool = True
    encryption_enabled: bool = False
    backup_directory: Optional[Path] = None
    database_enabled: bool = True
    file_enabled: bool = True
    validate_on_load: bool = True
    checksum_verification: bool = True


@dataclass
class StateSnapshot:
    """State snapshot data structure."""
    snapshot_id: str
    timestamp: datetime
    state_data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    checksum: Optional[str] = None
    compressed: bool = False
    encrypted: bool = False
    format: SerializationFormat = SerializationFormat.JSON
    size_bytes: int = 0


@dataclass
class PersistenceMetrics:
    """Metrics for persistence operations."""
    snapshots_created: int = 0
    snapshots_loaded: int = 0
    snapshots_deleted: int = 0
    auto_saves_performed: int = 0
    save_failures: int = 0
    load_failures: int = 0
    total_save_time: float = 0.0
    total_load_time: float = 0.0
    average_save_time: float = 0.0
    average_load_time: float = 0.0
    total_data_saved: int = 0  # bytes
    compression_ratio: float = 0.0


@dataclass
class StatePersistenceResult:
    """Result of persistence operations."""
    success: bool
    message: str
    snapshot_id: Optional[str] = None
    operation_time: float = 0.0
    data_size: int = 0
    errors: List[str] = field(default_factory=list)


class StatePersistenceManager:
    """
    State persistence manager for handling state serialization and recovery.
    
    Provides auto-save functionality, state recovery mechanisms, and integration
    with database storage for application state persistence.
    """
    
    def __init__(
        self,
        configuration: Optional[PersistenceConfiguration] = None,
        state_snapshots_db: Optional[Any] = None  # StateSnapshotsDB when available
    ):
        """Initialize the state persistence manager."""
        self._config = configuration or PersistenceConfiguration()
        self._db = state_snapshots_db
        self._lock = threading.RLock()
        self._metrics = PersistenceMetrics()
        self._logger = logging.getLogger(__name__)
        
        # Auto-save management
        self._auto_save_task: Optional[asyncio.Task] = None
        self._auto_save_enabled = False
        self._last_save_time: Optional[datetime] = None
        
        # State change tracking
        self._state_observers: List[Callable[[ApplicationState], None]] = []
        self._pending_changes = False
        
        # Snapshot cache
        self._snapshot_cache: Dict[str, StateSnapshot] = {}
        self._max_cache_size = 50
        
        # Initialize backup directory
        if self._config.backup_directory:
            self._config.backup_directory.mkdir(parents=True, exist_ok=True)
        
        # Start auto-save if enabled
        if self._config.mode in [PersistenceMode.AUTO_SAVE, PersistenceMode.CONTINUOUS]:
            self.start_auto_save()
    
    def save_state(
        self, 
        state: ApplicationState, 
        snapshot_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StatePersistenceResult:
        """
        Save application state to persistent storage.
        
        Args:
            state: Application state to save
            snapshot_id: Optional snapshot identifier
            metadata: Additional metadata
            
        Returns:
            Result of save operation
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            with self._lock:
                # Generate snapshot ID if not provided
                if not snapshot_id:
                    snapshot_id = f"snapshot_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
                
                # Serialize state data
                serialization_result = self._serialize_state(state)
                if not serialization_result.success:
                    return serialization_result
                
                # Create snapshot
                snapshot = StateSnapshot(
                    snapshot_id=snapshot_id,
                    timestamp=start_time,
                    state_data=serialization_result.data,
                    metadata=metadata or {},
                    format=self._config.format,
                    compressed=self._config.compression_enabled
                )
                
                # Calculate checksum if enabled
                if self._config.checksum_verification:
                    snapshot.checksum = self._calculate_checksum(serialization_result.data)
                
                # Save to storage
                save_result = self._save_snapshot(snapshot)
                if not save_result.success:
                    return save_result
                
                # Update cache
                self._update_cache(snapshot)
                
                # Update metrics
                operation_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                self._update_save_metrics(operation_time, save_result.data_size)
                
                self._last_save_time = start_time
                self._pending_changes = False
                
                self._logger.info(f"State saved successfully: {snapshot_id}")
                
                return StatePersistenceResult(
                    success=True,
                    message=f"State saved successfully as {snapshot_id}",
                    snapshot_id=snapshot_id,
                    operation_time=operation_time,
                    data_size=save_result.data_size
                )
                
        except Exception as e:
            self._metrics.save_failures += 1
            error_msg = f"Failed to save state: {e}"
            self._logger.error(error_msg)
            
            return StatePersistenceResult(
                success=False,
                message=error_msg,
                errors=[str(e)]
            )

    def load_state(self, snapshot_id: str) -> StatePersistenceResult:
        """
        Load application state from persistent storage.

        Args:
            snapshot_id: Snapshot identifier to load

        Returns:
            Result containing loaded state data
        """
        start_time = datetime.now(timezone.utc)

        try:
            with self._lock:
                # Check cache first
                if snapshot_id in self._snapshot_cache:
                    snapshot = self._snapshot_cache[snapshot_id]
                    self._logger.info(f"State loaded from cache: {snapshot_id}")
                else:
                    # Load from storage
                    load_result = self._load_snapshot(snapshot_id)
                    if not load_result.success:
                        return load_result
                    snapshot = load_result.snapshot

                # Validate checksum if enabled
                if self._config.checksum_verification and snapshot.checksum:
                    calculated_checksum = self._calculate_checksum(snapshot.state_data)
                    if calculated_checksum != snapshot.checksum:
                        return StatePersistenceResult(
                            success=False,
                            message=f"Checksum validation failed for snapshot {snapshot_id}",
                            errors=["Checksum mismatch"]
                        )

                # Deserialize state data
                deserialization_result = self._deserialize_state(snapshot.state_data, snapshot.format)
                if not deserialization_result.success:
                    return deserialization_result

                # Update metrics
                operation_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                self._update_load_metrics(operation_time)

                self._logger.info(f"State loaded successfully: {snapshot_id}")

                return StatePersistenceResult(
                    success=True,
                    message=f"State loaded successfully from {snapshot_id}",
                    snapshot_id=snapshot_id,
                    operation_time=operation_time,
                    data_size=snapshot.size_bytes
                )

        except Exception as e:
            self._metrics.load_failures += 1
            error_msg = f"Failed to load state: {e}"
            self._logger.error(error_msg)

            return StatePersistenceResult(
                success=False,
                message=error_msg,
                errors=[str(e)]
            )

    def list_snapshots(self, limit: Optional[int] = None) -> List[StateSnapshot]:
        """
        List available state snapshots.

        Args:
            limit: Maximum number of snapshots to return

        Returns:
            List of available snapshots
        """
        try:
            with self._lock:
                snapshots = []

                # Get from database if enabled
                if self._config.database_enabled and self._db:
                    db_snapshots = self._db.list_snapshots(limit=limit)
                    for db_snapshot in db_snapshots:
                        snapshot = StateSnapshot(
                            snapshot_id=db_snapshot['snapshot_id'],
                            timestamp=datetime.fromisoformat(db_snapshot['created_at']),
                            state_data=json.loads(db_snapshot['state_data']),
                            metadata=json.loads(db_snapshot.get('metadata', '{}')),
                            checksum=db_snapshot.get('checksum'),
                            size_bytes=len(db_snapshot['state_data'])
                        )
                        snapshots.append(snapshot)

                # Sort by timestamp (newest first)
                snapshots.sort(key=lambda x: x.timestamp, reverse=True)

                if limit:
                    snapshots = snapshots[:limit]

                return snapshots

        except Exception as e:
            self._logger.error(f"Failed to list snapshots: {e}")
            return []

    def delete_snapshot(self, snapshot_id: str) -> StatePersistenceResult:
        """
        Delete a state snapshot.

        Args:
            snapshot_id: Snapshot identifier to delete

        Returns:
            Result of delete operation
        """
        try:
            with self._lock:
                # Remove from cache
                if snapshot_id in self._snapshot_cache:
                    del self._snapshot_cache[snapshot_id]

                # Delete from database
                if self._config.database_enabled and self._db:
                    self._db.delete_snapshot(snapshot_id)

                # Delete file if exists
                if self._config.file_enabled and self._config.backup_directory:
                    file_path = self._config.backup_directory / f"{snapshot_id}.json"
                    if file_path.exists():
                        file_path.unlink()

                self._metrics.snapshots_deleted += 1
                self._logger.info(f"Snapshot deleted: {snapshot_id}")

                return StatePersistenceResult(
                    success=True,
                    message=f"Snapshot {snapshot_id} deleted successfully",
                    snapshot_id=snapshot_id
                )

        except Exception as e:
            error_msg = f"Failed to delete snapshot: {e}"
            self._logger.error(error_msg)

            return StatePersistenceResult(
                success=False,
                message=error_msg,
                errors=[str(e)]
            )

    def start_auto_save(self) -> None:
        """Start auto-save functionality."""
        if not self._auto_save_enabled:
            self._auto_save_enabled = True
            self._logger.info("Auto-save started")

    def stop_auto_save(self) -> None:
        """Stop auto-save functionality."""
        if self._auto_save_enabled:
            self._auto_save_enabled = False
            if self._auto_save_task:
                self._auto_save_task.cancel()
            self._logger.info("Auto-save stopped")

    def cleanup_old_snapshots(self, max_age_days: int = 30) -> int:
        """
        Clean up old snapshots.

        Args:
            max_age_days: Maximum age in days for snapshots

        Returns:
            Number of snapshots deleted
        """
        try:
            with self._lock:
                cutoff_date = datetime.now(timezone.utc).replace(
                    day=datetime.now(timezone.utc).day - max_age_days
                )

                snapshots = self.list_snapshots()
                deleted_count = 0

                for snapshot in snapshots:
                    if snapshot.timestamp < cutoff_date:
                        result = self.delete_snapshot(snapshot.snapshot_id)
                        if result.success:
                            deleted_count += 1

                self._logger.info(f"Cleaned up {deleted_count} old snapshots")
                return deleted_count

        except Exception as e:
            self._logger.error(f"Failed to cleanup old snapshots: {e}")
            return 0

    def _serialize_state(self, state: ApplicationState) -> 'SerializationResult':
        """Serialize application state to storage format."""
        try:
            # Convert state to dictionary
            state_dict = {
                'state_id': state.state_id,
                'current_state': state.current_state.value,
                'previous_state': state.previous_state.value if state.previous_state else None,
                'state_timestamp': state.state_timestamp.isoformat(),
                'session_id': state.session_id,
                'startup_timestamp': state.startup_timestamp.isoformat(),
                'active_project': state.active_project,
                'loaded_models': state.loaded_models,
                'resource_allocation': state.resource_allocation,
                'ui_state': state.ui_state,
                'background_tasks': state.background_tasks,
                'user_preferences': state.user_preferences,
                'transition_count': state.transition_count,
                'error_count': state.error_count,
                'last_error': state.last_error,
                'state_history': state.state_history,
                'is_initialized': state.is_initialized,
                'is_shutting_down': state.is_shutting_down,
                'recovery_mode': state.recovery_mode
            }

            # Serialize based on format
            if self._config.format == SerializationFormat.JSON:
                data = json.dumps(state_dict, indent=2, ensure_ascii=False)
            elif self._config.format == SerializationFormat.PICKLE:
                data = pickle.dumps(state_dict)
            elif self._config.format == SerializationFormat.COMPRESSED_JSON:
                json_data = json.dumps(state_dict, ensure_ascii=False)
                data = gzip.compress(json_data.encode('utf-8'))
            elif self._config.format == SerializationFormat.COMPRESSED_PICKLE:
                pickle_data = pickle.dumps(state_dict)
                data = gzip.compress(pickle_data)
            else:
                raise ValueError(f"Unsupported serialization format: {self._config.format}")

            return SerializationResult(success=True, data=data, size=len(data))

        except Exception as e:
            return SerializationResult(
                success=False,
                message=f"Serialization failed: {e}",
                errors=[str(e)]
            )

    def _deserialize_state(self, data: Any, format: SerializationFormat) -> 'DeserializationResult':
        """Deserialize state data from storage format."""
        try:
            # Deserialize based on format
            if format == SerializationFormat.JSON:
                if isinstance(data, str):
                    state_dict = json.loads(data)
                else:
                    state_dict = data
            elif format == SerializationFormat.PICKLE:
                state_dict = pickle.loads(data)
            elif format == SerializationFormat.COMPRESSED_JSON:
                json_data = gzip.decompress(data).decode('utf-8')
                state_dict = json.loads(json_data)
            elif format == SerializationFormat.COMPRESSED_PICKLE:
                pickle_data = gzip.decompress(data)
                state_dict = pickle.loads(pickle_data)
            else:
                raise ValueError(f"Unsupported deserialization format: {format}")

            # Convert back to ApplicationState
            ApplicationState, ApplicationStateType = _get_application_state_types()
            state = ApplicationState(
                state_id=state_dict['state_id'],
                current_state=ApplicationStateType(state_dict['current_state']),
                previous_state=ApplicationStateType(state_dict['previous_state']) if state_dict['previous_state'] else None,
                state_timestamp=datetime.fromisoformat(state_dict['state_timestamp']),
                session_id=state_dict['session_id'],
                startup_timestamp=datetime.fromisoformat(state_dict['startup_timestamp']),
                active_project=state_dict['active_project'],
                loaded_models=state_dict['loaded_models'],
                resource_allocation=state_dict['resource_allocation'],
                ui_state=state_dict['ui_state'],
                background_tasks=state_dict['background_tasks'],
                user_preferences=state_dict['user_preferences'],
                transition_count=state_dict['transition_count'],
                error_count=state_dict['error_count'],
                last_error=state_dict['last_error'],
                state_history=state_dict['state_history'],
                is_initialized=state_dict['is_initialized'],
                is_shutting_down=state_dict['is_shutting_down'],
                recovery_mode=state_dict['recovery_mode']
            )

            return DeserializationResult(success=True, state=state)

        except Exception as e:
            return DeserializationResult(
                success=False,
                message=f"Deserialization failed: {e}",
                errors=[str(e)]
            )

    def _save_snapshot(self, snapshot: StateSnapshot) -> 'SaveResult':
        """Save snapshot to storage."""
        try:
            data_size = 0

            # Save to database if enabled
            if self._config.database_enabled and self._db:
                snapshot_data = {
                    'snapshot_id': snapshot.snapshot_id,
                    'state_data': json.dumps(snapshot.state_data) if isinstance(snapshot.state_data, dict) else snapshot.state_data,
                    'metadata': json.dumps(snapshot.metadata),
                    'checksum': snapshot.checksum,
                    'format': snapshot.format.value,
                    'compressed': snapshot.compressed,
                    'encrypted': snapshot.encrypted
                }
                self._db.save_snapshot(snapshot_data)
                data_size += len(str(snapshot_data))

            # Save to file if enabled
            if self._config.file_enabled and self._config.backup_directory:
                file_path = self._config.backup_directory / f"{snapshot.snapshot_id}.json"
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'snapshot_id': snapshot.snapshot_id,
                        'timestamp': snapshot.timestamp.isoformat(),
                        'state_data': snapshot.state_data,
                        'metadata': snapshot.metadata,
                        'checksum': snapshot.checksum,
                        'format': snapshot.format.value
                    }, f, indent=2, ensure_ascii=False)
                data_size += file_path.stat().st_size

            snapshot.size_bytes = data_size
            return SaveResult(success=True, data_size=data_size)

        except Exception as e:
            return SaveResult(
                success=False,
                message=f"Failed to save snapshot: {e}",
                errors=[str(e)]
            )

    def _load_snapshot(self, snapshot_id: str) -> 'LoadResult':
        """Load snapshot from storage."""
        try:
            # Try database first
            if self._config.database_enabled and self._db:
                db_snapshot = self._db.get_snapshot(snapshot_id)
                if db_snapshot:
                    snapshot = StateSnapshot(
                        snapshot_id=db_snapshot['snapshot_id'],
                        timestamp=datetime.fromisoformat(db_snapshot['created_at']),
                        state_data=json.loads(db_snapshot['state_data']),
                        metadata=json.loads(db_snapshot.get('metadata', '{}')),
                        checksum=db_snapshot.get('checksum'),
                        format=SerializationFormat(db_snapshot.get('format', 'JSON')),
                        compressed=db_snapshot.get('compressed', False),
                        encrypted=db_snapshot.get('encrypted', False),
                        size_bytes=len(db_snapshot['state_data'])
                    )
                    return LoadResult(success=True, snapshot=snapshot)

            # Try file system
            if self._config.file_enabled and self._config.backup_directory:
                file_path = self._config.backup_directory / f"{snapshot_id}.json"
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    snapshot = StateSnapshot(
                        snapshot_id=data['snapshot_id'],
                        timestamp=datetime.fromisoformat(data['timestamp']),
                        state_data=data['state_data'],
                        metadata=data['metadata'],
                        checksum=data.get('checksum'),
                        format=SerializationFormat(data.get('format', 'JSON')),
                        size_bytes=file_path.stat().st_size
                    )
                    return LoadResult(success=True, snapshot=snapshot)

            return LoadResult(
                success=False,
                message=f"Snapshot not found: {snapshot_id}"
            )

        except Exception as e:
            return LoadResult(
                success=False,
                message=f"Failed to load snapshot: {e}",
                errors=[str(e)]
            )

    def _calculate_checksum(self, data: Any) -> str:
        """Calculate checksum for data integrity verification."""
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        else:
            data_str = str(data)

        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

    def _update_cache(self, snapshot: StateSnapshot) -> None:
        """Update snapshot cache."""
        self._snapshot_cache[snapshot.snapshot_id] = snapshot

        # Limit cache size
        if len(self._snapshot_cache) > self._max_cache_size:
            # Remove oldest entries
            sorted_snapshots = sorted(
                self._snapshot_cache.items(),
                key=lambda x: x[1].timestamp
            )
            for snapshot_id, _ in sorted_snapshots[:len(self._snapshot_cache) - self._max_cache_size]:
                del self._snapshot_cache[snapshot_id]

    def _update_save_metrics(self, operation_time: float, data_size: int) -> None:
        """Update save operation metrics."""
        self._metrics.snapshots_created += 1
        self._metrics.total_save_time += operation_time
        self._metrics.total_data_saved += data_size

        if self._metrics.snapshots_created > 0:
            self._metrics.average_save_time = self._metrics.total_save_time / self._metrics.snapshots_created

    def _update_load_metrics(self, operation_time: float) -> None:
        """Update load operation metrics."""
        self._metrics.snapshots_loaded += 1
        self._metrics.total_load_time += operation_time

        if self._metrics.snapshots_loaded > 0:
            self._metrics.average_load_time = self._metrics.total_load_time / self._metrics.snapshots_loaded

    def get_metrics(self) -> PersistenceMetrics:
        """
        Get persistence metrics.

        Returns:
            Current persistence metrics
        """
        with self._lock:
            return self._metrics

    def add_state_observer(self, callback: Callable[['ApplicationState'], None]) -> None:
        """
        Add state change observer for auto-save triggering.

        Args:
            callback: Function to call on state changes
        """
        if callback not in self._state_observers:
            self._state_observers.append(callback)

    def remove_state_observer(self, callback: Callable[['ApplicationState'], None]) -> None:
        """
        Remove state change observer.

        Args:
            callback: Function to remove from observers
        """
        if callback in self._state_observers:
            self._state_observers.remove(callback)

    def on_state_change(self, state: 'ApplicationState') -> None:
        """
        Handle state change notification for auto-save.

        Args:
            state: Changed application state
        """
        if self._config.mode == PersistenceMode.ON_CHANGE:
            self.save_state(state)
        elif self._config.mode in [PersistenceMode.AUTO_SAVE, PersistenceMode.CONTINUOUS]:
            self._pending_changes = True


# Helper result classes
@dataclass
class SerializationResult:
    """Result of serialization operation."""
    success: bool
    data: Any = None
    size: int = 0
    message: str = ""
    errors: List[str] = field(default_factory=list)


@dataclass
class DeserializationResult:
    """Result of deserialization operation."""
    success: bool
    state: Optional['ApplicationState'] = None
    message: str = ""
    errors: List[str] = field(default_factory=list)


@dataclass
class SaveResult:
    """Result of save operation."""
    success: bool
    data_size: int = 0
    message: str = ""
    errors: List[str] = field(default_factory=list)


@dataclass
class LoadResult:
    """Result of load operation."""
    success: bool
    snapshot: Optional[StateSnapshot] = None
    message: str = ""
    errors: List[str] = field(default_factory=list)
