"""
Module: state_snapshotter_lg
Description: Creates and manages application state snapshots with incremental snapshots, compression, and restoration
Phase: 4
Location: /src/modules/logic/backup_recovery_lg/state_snapshotter_lg/
"""

# Standard library imports
import hashlib
import json
import pickle
import threading
import time
import uuid
import zlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import tempfile

# Local imports
from ..base_interfaces import (
    IStateSnapshotter, SnapshotConfig, SnapshotResult, SnapshotType
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg import get_logger


class SnapshotCompressor:
    """Handles snapshot compression operations."""
    
    def __init__(self):
        """Initialize snapshot compressor."""
        self._logger = get_logger(__name__)
    
    def compress_state_data(self, state_data: Dict[str, Any], compression_level: int = 6) -> bytes:
        """
        Compress state data.
        
        Args:
            state_data: State data to compress
            compression_level: Compression level (1-9)
            
        Returns:
            Compressed data bytes
        """
        try:
            # Serialize state data
            serialized_data = json.dumps(state_data, ensure_ascii=False).encode('utf-8')
            
            # Compress data
            compressed_data = zlib.compress(serialized_data, compression_level)
            
            return compressed_data
            
        except Exception as e:
            self._logger.error(f"Failed to compress state data: {e}")
            # Return uncompressed data as fallback
            return json.dumps(state_data, ensure_ascii=False).encode('utf-8')
    
    def decompress_state_data(self, compressed_data: bytes) -> Dict[str, Any]:
        """
        Decompress state data.
        
        Args:
            compressed_data: Compressed data bytes
            
        Returns:
            Decompressed state data
        """
        try:
            # Try to decompress
            try:
                decompressed_data = zlib.decompress(compressed_data)
                return json.loads(decompressed_data.decode('utf-8'))
            except zlib.error:
                # Data might not be compressed, try direct JSON decode
                return json.loads(compressed_data.decode('utf-8'))
                
        except Exception as e:
            self._logger.error(f"Failed to decompress state data: {e}")
            return {}
    
    def calculate_compression_ratio(self, original_size: int, compressed_size: int) -> float:
        """Calculate compression ratio."""
        if original_size == 0:
            return 0.0
        return compressed_size / original_size


class IncrementalSnapshotter:
    """Handles incremental snapshot operations."""
    
    def __init__(self):
        """Initialize incremental snapshotter."""
        self._logger = get_logger(__name__)
    
    def create_incremental_snapshot(self, current_state: Dict[str, Any], 
                                   previous_snapshot_path: Optional[Path]) -> Dict[str, Any]:
        """
        Create incremental snapshot by comparing with previous state.
        
        Args:
            current_state: Current state data
            previous_snapshot_path: Path to previous snapshot
            
        Returns:
            Incremental state data (only changes)
        """
        try:
            if not previous_snapshot_path or not previous_snapshot_path.exists():
                # No previous snapshot, return full state
                return current_state
            
            # Load previous state
            with open(previous_snapshot_path, 'r') as f:
                snapshot_data = json.load(f)
            
            previous_state = snapshot_data.get('state_data', {})
            
            # Calculate differences
            incremental_data = self._calculate_state_diff(previous_state, current_state)
            
            return incremental_data
            
        except Exception as e:
            self._logger.error(f"Failed to create incremental snapshot: {e}")
            # Return full state as fallback
            return current_state
    
    def _calculate_state_diff(self, previous_state: Dict[str, Any], 
                             current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate differences between states."""
        diff = {}
        
        try:
            # Find added/modified keys
            for key, value in current_state.items():
                if key not in previous_state or previous_state[key] != value:
                    diff[key] = value
            
            # Mark deleted keys
            deleted_keys = []
            for key in previous_state:
                if key not in current_state:
                    deleted_keys.append(key)
            
            if deleted_keys:
                diff['__deleted_keys__'] = deleted_keys
            
            return diff
            
        except Exception as e:
            self._logger.error(f"Failed to calculate state diff: {e}")
            return current_state
    
    def apply_incremental_snapshot(self, base_state: Dict[str, Any], 
                                  incremental_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply incremental snapshot to base state.
        
        Args:
            base_state: Base state data
            incremental_data: Incremental changes
            
        Returns:
            Reconstructed state
        """
        try:
            result_state = base_state.copy()
            
            # Apply changes
            for key, value in incremental_data.items():
                if key != '__deleted_keys__':
                    result_state[key] = value
            
            # Remove deleted keys
            deleted_keys = incremental_data.get('__deleted_keys__', [])
            for key in deleted_keys:
                result_state.pop(key, None)
            
            return result_state
            
        except Exception as e:
            self._logger.error(f"Failed to apply incremental snapshot: {e}")
            return base_state
    
    def find_base_snapshot(self, snapshot_directory: Path, snapshot_id: str) -> Optional[Path]:
        """Find base snapshot for incremental reconstruction."""
        try:
            # Look for snapshot metadata to find parent
            snapshot_path = snapshot_directory / f"{snapshot_id}.json"
            if snapshot_path.exists():
                with open(snapshot_path, 'r') as f:
                    metadata = json.load(f)
                
                parent_snapshot = metadata.get('parent_snapshot')
                if parent_snapshot:
                    parent_path = snapshot_directory / f"{parent_snapshot}.json"
                    if parent_path.exists():
                        return parent_path
            
            return None
            
        except Exception as e:
            self._logger.error(f"Failed to find base snapshot: {e}")
            return None


class SnapshotManager:
    """Manages snapshot lifecycle and operations."""
    
    def __init__(self):
        """Initialize snapshot manager."""
        self._logger = get_logger(__name__)
        self._compressor = SnapshotCompressor()
        self._incremental_snapshotter = IncrementalSnapshotter()
    
    def create_snapshot_file(self, state_data: Dict[str, Any], snapshot_config: SnapshotConfig, 
                           snapshot_result: SnapshotResult) -> bool:
        """
        Create snapshot file.
        
        Args:
            state_data: State data to snapshot
            snapshot_config: Snapshot configuration
            snapshot_result: Snapshot result to update
            
        Returns:
            True if snapshot creation successful
        """
        try:
            # Ensure snapshot directory exists
            snapshot_config.snapshot_directory.mkdir(parents=True, exist_ok=True)
            
            # Determine if this should be incremental
            incremental_data = state_data
            parent_snapshot = None
            
            if snapshot_config.incremental_enabled:
                # Find latest snapshot for incremental comparison
                latest_snapshot = self._find_latest_snapshot(snapshot_config.snapshot_directory)
                if latest_snapshot:
                    incremental_data = self._incremental_snapshotter.create_incremental_snapshot(
                        state_data, latest_snapshot
                    )
                    parent_snapshot = latest_snapshot.stem
                    snapshot_result.is_incremental = True
                    snapshot_result.parent_snapshot = parent_snapshot
            
            # Create snapshot metadata
            snapshot_metadata = {
                'snapshot_id': snapshot_result.snapshot_id,
                'snapshot_type': snapshot_result.snapshot_type.value,
                'timestamp': snapshot_result.start_time.isoformat(),
                'is_incremental': snapshot_result.is_incremental,
                'parent_snapshot': parent_snapshot,
                'compression_enabled': snapshot_config.compression_enabled,
                'state_data': incremental_data
            }
            
            # Compress if enabled
            if snapshot_config.compression_enabled:
                original_data = json.dumps(snapshot_metadata, ensure_ascii=False).encode('utf-8')
                compressed_data = self._compressor.compress_state_data(incremental_data)
                
                # Update metadata with compression info
                snapshot_metadata['compressed'] = True
                snapshot_metadata['original_size'] = len(original_data)
                snapshot_metadata['compressed_size'] = len(compressed_data)
                snapshot_metadata['state_data'] = compressed_data.hex()  # Store as hex string
            
            # Save snapshot
            with open(snapshot_result.snapshot_path, 'w') as f:
                json.dump(snapshot_metadata, f, indent=2, ensure_ascii=False)
            
            # Calculate size and checksum
            snapshot_result.size_bytes = snapshot_result.snapshot_path.stat().st_size
            snapshot_result.checksum = self._calculate_checksum(snapshot_result.snapshot_path)
            
            return True
            
        except Exception as e:
            snapshot_result.add_error(f"Snapshot creation failed: {e}")
            return False
    
    def load_snapshot_file(self, snapshot_path: Path) -> Optional[Dict[str, Any]]:
        """
        Load snapshot from file.
        
        Args:
            snapshot_path: Path to snapshot file
            
        Returns:
            Snapshot data or None if failed
        """
        try:
            if not snapshot_path.exists():
                return None
            
            with open(snapshot_path, 'r') as f:
                snapshot_metadata = json.load(f)
            
            state_data = snapshot_metadata.get('state_data', {})
            
            # Handle compressed data
            if snapshot_metadata.get('compressed', False):
                if isinstance(state_data, str):
                    # Decompress hex-encoded data
                    compressed_data = bytes.fromhex(state_data)
                    state_data = self._compressor.decompress_state_data(compressed_data)
            
            # Handle incremental snapshots
            if snapshot_metadata.get('is_incremental', False):
                parent_snapshot = snapshot_metadata.get('parent_snapshot')
                if parent_snapshot:
                    parent_path = snapshot_path.parent / f"{parent_snapshot}.json"
                    base_state = self.load_snapshot_file(parent_path)
                    
                    if base_state:
                        state_data = self._incremental_snapshotter.apply_incremental_snapshot(
                            base_state, state_data
                        )
            
            return state_data
            
        except Exception as e:
            self._logger.error(f"Failed to load snapshot {snapshot_path}: {e}")
            return None
    
    def _find_latest_snapshot(self, snapshot_directory: Path) -> Optional[Path]:
        """Find the latest snapshot in directory."""
        try:
            if not snapshot_directory.exists():
                return None
            
            latest_snapshot = None
            latest_time = None
            
            for snapshot_file in snapshot_directory.glob("*.json"):
                try:
                    with open(snapshot_file, 'r') as f:
                        metadata = json.load(f)
                    
                    timestamp = metadata.get('timestamp')
                    if timestamp:
                        snapshot_time = datetime.fromisoformat(timestamp)
                        
                        if latest_time is None or snapshot_time > latest_time:
                            latest_time = snapshot_time
                            latest_snapshot = snapshot_file
                            
                except Exception:
                    continue
            
            return latest_snapshot
            
        except Exception as e:
            self._logger.error(f"Failed to find latest snapshot: {e}")
            return None
    
    def _calculate_checksum(self, file_path: Path, algorithm: str = "sha256") -> Optional[str]:
        """Calculate file checksum."""
        try:
            hash_obj = hashlib.new(algorithm)
            
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
            
        except Exception as e:
            self._logger.error(f"Failed to calculate checksum for {file_path}: {e}")
            return None
    
    def validate_snapshot(self, snapshot_path: Path) -> bool:
        """
        Validate snapshot integrity.
        
        Args:
            snapshot_path: Path to snapshot
            
        Returns:
            True if snapshot is valid
        """
        try:
            if not snapshot_path.exists():
                return False
            
            # Try to load snapshot
            snapshot_data = self.load_snapshot_file(snapshot_path)
            return snapshot_data is not None
            
        except Exception as e:
            self._logger.error(f"Failed to validate snapshot {snapshot_path}: {e}")
            return False


class StateSnapshotter(IStateSnapshotter):
    """
    Comprehensive state snapshotter for creating and managing application state snapshots.

    Features:
    - Multiple snapshot types (application, system, user, configuration)
    - Incremental snapshots with delta compression
    - Compression and memory-efficient operations
    - Automatic cleanup and retention policies
    - Metadata tracking and indexing
    - Integrity verification
    - Comprehensive error handling and logging
    """

    def __init__(self):
        """Initialize state snapshotter."""
        self._logger = get_logger(__name__)
        self._snapshot_manager = SnapshotManager()
        self._compressor = SnapshotCompressor()
        self._incremental_snapshotter = IncrementalSnapshotter()

        # Thread safety
        self._lock = threading.RLock()

        # Snapshot tracking
        self._active_snapshots: Dict[str, SnapshotResult] = {}
        self._snapshot_history: List[SnapshotResult] = []
        self._snapshot_cache: Dict[str, Dict[str, Any]] = {}

        # Auto-snapshot timer
        self._auto_snapshot_timer: Optional[threading.Timer] = None
        self._auto_snapshot_enabled = False

        self._logger.info("StateSnapshotter initialized")

    def create_snapshot(self, state_data: Dict[str, Any], snapshot_config: SnapshotConfig) -> SnapshotResult:
        """
        Create state snapshot.

        Args:
            state_data: State data to snapshot
            snapshot_config: Snapshot configuration

        Returns:
            SnapshotResult with operation details
        """
        snapshot_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)

        # Generate snapshot filename
        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        snapshot_filename = f"snapshot_{timestamp}_{snapshot_id[:8]}.json"
        snapshot_path = snapshot_config.snapshot_directory / snapshot_filename

        result = SnapshotResult(
            success=False,
            snapshot_id=snapshot_id,
            snapshot_path=snapshot_path,
            snapshot_type=snapshot_config.snapshot_type,
            start_time=start_time
        )

        try:
            with self._lock:
                self._active_snapshots[snapshot_id] = result

            # Validate state data
            if not state_data:
                result.add_warning("Empty state data provided")

            # Check available space if memory efficient mode
            if snapshot_config.memory_efficient:
                if not self._check_memory_usage():
                    result.add_warning("High memory usage detected")

            # Create snapshot
            success = self._snapshot_manager.create_snapshot_file(state_data, snapshot_config, result)

            if success:
                # Validate snapshot
                if self._snapshot_manager.validate_snapshot(result.snapshot_path):
                    result.success = True

                    # Cache snapshot if enabled
                    if snapshot_config.metadata_tracking:
                        with self._lock:
                            self._snapshot_cache[snapshot_id] = state_data.copy()

                    self._logger.info(f"Snapshot created successfully: {snapshot_id}")
                else:
                    result.add_error("Snapshot validation failed")

            result.end_time = datetime.now(timezone.utc)

            # Add to history
            with self._lock:
                self._snapshot_history.append(result)
                if snapshot_id in self._active_snapshots:
                    del self._active_snapshots[snapshot_id]

            # Cleanup old snapshots if auto-cleanup enabled
            if result.success and snapshot_config.auto_cleanup:
                self.cleanup_snapshots(snapshot_config)

            # Start auto-snapshot if configured
            if snapshot_config.snapshot_interval > 0 and not self._auto_snapshot_enabled:
                self._start_auto_snapshot(state_data, snapshot_config)

            return result

        except Exception as e:
            result.add_error(f"Snapshot creation failed: {e}")
            result.end_time = datetime.now(timezone.utc)
            self._logger.error(f"Snapshot {snapshot_id} failed: {e}", exc_info=True)

            with self._lock:
                if snapshot_id in self._active_snapshots:
                    del self._active_snapshots[snapshot_id]

            return result

    def restore_snapshot(self, snapshot_path: Path) -> Dict[str, Any]:
        """
        Restore state from snapshot.

        Args:
            snapshot_path: Path to snapshot

        Returns:
            Restored state data
        """
        try:
            if not snapshot_path.exists():
                self._logger.error(f"Snapshot does not exist: {snapshot_path}")
                return {}

            # Load snapshot data
            state_data = self._snapshot_manager.load_snapshot_file(snapshot_path)

            if state_data is not None:
                self._logger.info(f"Snapshot restored successfully: {snapshot_path}")
                return state_data
            else:
                self._logger.error(f"Failed to restore snapshot: {snapshot_path}")
                return {}

        except Exception as e:
            self._logger.error(f"Failed to restore snapshot {snapshot_path}: {e}")
            return {}

    def list_snapshots(self, snapshot_directory: Path) -> List[Dict[str, Any]]:
        """
        List available snapshots.

        Args:
            snapshot_directory: Directory containing snapshots

        Returns:
            List of snapshot metadata
        """
        snapshots = []

        try:
            if not snapshot_directory.exists():
                return snapshots

            for snapshot_file in snapshot_directory.glob("*.json"):
                try:
                    with open(snapshot_file, 'r') as f:
                        metadata = json.load(f)

                    # Add file system info
                    metadata['snapshot_path'] = str(snapshot_file)
                    metadata['file_size'] = snapshot_file.stat().st_size
                    metadata['last_modified'] = datetime.fromtimestamp(
                        snapshot_file.stat().st_mtime, tz=timezone.utc
                    ).isoformat()

                    # Add validation status
                    metadata['is_valid'] = self._snapshot_manager.validate_snapshot(snapshot_file)

                    snapshots.append(metadata)

                except Exception as e:
                    self._logger.warning(f"Failed to read snapshot metadata {snapshot_file}: {e}")

            # Sort by timestamp (newest first)
            snapshots.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        except Exception as e:
            self._logger.error(f"Failed to list snapshots: {e}")

        return snapshots

    def cleanup_snapshots(self, snapshot_config: SnapshotConfig) -> int:
        """
        Clean up old snapshots.

        Args:
            snapshot_config: Snapshot configuration

        Returns:
            Number of snapshots cleaned up
        """
        cleaned_count = 0

        try:
            snapshots = self.list_snapshots(snapshot_config.snapshot_directory)

            # Sort by timestamp (oldest first for cleanup)
            snapshots.sort(key=lambda x: x.get('timestamp', ''))

            # Apply cleanup policies
            cutoff_date = datetime.now(timezone.utc) - timedelta(
                seconds=snapshot_config.snapshot_interval * snapshot_config.max_snapshots
            )

            for snapshot in snapshots:
                try:
                    snapshot_time = datetime.fromisoformat(snapshot['timestamp'])
                    snapshot_path = Path(snapshot['snapshot_path'])

                    # Check if snapshot should be cleaned up
                    should_cleanup = False

                    # Time-based cleanup
                    if snapshot_time < cutoff_date:
                        should_cleanup = True

                    # Count-based cleanup (keep only N most recent)
                    if len(snapshots) - cleaned_count > snapshot_config.max_snapshots:
                        should_cleanup = True

                    if should_cleanup and snapshot_path.exists():
                        snapshot_path.unlink()
                        cleaned_count += 1
                        self._logger.info(f"Cleaned up old snapshot: {snapshot_path}")

                        # Remove from cache
                        snapshot_id = snapshot.get('snapshot_id')
                        if snapshot_id:
                            with self._lock:
                                self._snapshot_cache.pop(snapshot_id, None)

                except Exception as e:
                    self._logger.warning(f"Failed to cleanup snapshot {snapshot.get('snapshot_path')}: {e}")

        except Exception as e:
            self._logger.error(f"Failed to cleanup snapshots: {e}")

        return cleaned_count

    def _check_memory_usage(self) -> bool:
        """Check if memory usage is acceptable."""
        try:
            import psutil
            memory_percent = psutil.virtual_memory().percent
            return memory_percent < 80  # Consider 80% as high usage
        except ImportError:
            # psutil not available, assume memory is OK
            return True
        except Exception as e:
            self._logger.warning(f"Failed to check memory usage: {e}")
            return True

    def _start_auto_snapshot(self, state_data: Dict[str, Any], snapshot_config: SnapshotConfig) -> None:
        """Start automatic snapshot timer."""
        try:
            if not self._auto_snapshot_enabled and snapshot_config.snapshot_interval > 0:
                self._auto_snapshot_enabled = True

                def auto_snapshot():
                    try:
                        if self._auto_snapshot_enabled:
                            self.create_snapshot(state_data, snapshot_config)
                            # Schedule next snapshot
                            self._auto_snapshot_timer = threading.Timer(
                                snapshot_config.snapshot_interval, auto_snapshot
                            )
                            self._auto_snapshot_timer.daemon = True
                            self._auto_snapshot_timer.start()
                    except Exception as e:
                        self._logger.error(f"Auto-snapshot failed: {e}")

                self._auto_snapshot_timer = threading.Timer(
                    snapshot_config.snapshot_interval, auto_snapshot
                )
                self._auto_snapshot_timer.daemon = True
                self._auto_snapshot_timer.start()

                self._logger.info(f"Auto-snapshot started with interval: {snapshot_config.snapshot_interval}s")

        except Exception as e:
            self._logger.error(f"Failed to start auto-snapshot: {e}")

    def stop_auto_snapshot(self) -> None:
        """Stop automatic snapshot timer."""
        try:
            self._auto_snapshot_enabled = False
            if self._auto_snapshot_timer:
                self._auto_snapshot_timer.cancel()
                self._auto_snapshot_timer = None

            self._logger.info("Auto-snapshot stopped")

        except Exception as e:
            self._logger.error(f"Failed to stop auto-snapshot: {e}")

    def get_snapshot_status(self, snapshot_id: str) -> Optional[SnapshotResult]:
        """
        Get status of active snapshot operation.

        Args:
            snapshot_id: Snapshot identifier

        Returns:
            SnapshotResult or None if not found
        """
        with self._lock:
            return self._active_snapshots.get(snapshot_id)

    def get_snapshot_history(self) -> List[SnapshotResult]:
        """
        Get snapshot operation history.

        Returns:
            List of completed snapshot results
        """
        with self._lock:
            return self._snapshot_history.copy()

    def get_cached_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached snapshot data.

        Args:
            snapshot_id: Snapshot identifier

        Returns:
            Cached snapshot data or None if not found
        """
        with self._lock:
            return self._snapshot_cache.get(snapshot_id)

    def clear_snapshot_cache(self) -> None:
        """Clear snapshot cache."""
        with self._lock:
            self._snapshot_cache.clear()
        self._logger.info("Snapshot cache cleared")
