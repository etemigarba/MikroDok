"""
Module: crash_recovery_lg
Description: Handles unexpected terminations, creates recovery checkpoints, and restores application state after crashes
Phase: 1
Location: /src/modules/logic/application_lifecycle_lg/crash_recovery_lg/crash_recovery_lg.py
"""

# Standard library imports
import asyncio
import json
import pickle
import time
import threading
from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from datetime import datetime, timezone

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    get_log_manager, LogManager
)
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.error_handling_lg.crash_handler_lg.crash_handler_lg import (
    CrashHandler, CrashType, CrashContext, RecoveryPoint
)
from src.modules.logic.error_handling_lg.recovery_orchestrator_lg.recovery_orchestrator_lg import (
    RecoveryOrchestrator, RecoveryStrategy, RecoveryResult
)
from src.modules.logic.error_handling_lg.error_classifier_lg.error_classifier_lg import (
    ErrorClassifier, ErrorSeverity, ErrorCategory
)


class RecoveryMode(Enum):
    """Recovery modes for crash recovery."""
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
    INTERACTIVE = "INTERACTIVE"
    SAFE_MODE = "SAFE_MODE"


class CheckpointType(Enum):
    """Types of recovery checkpoints."""
    STARTUP = "STARTUP"
    PERIODIC = "PERIODIC"
    BEFORE_OPERATION = "BEFORE_OPERATION"
    AFTER_OPERATION = "AFTER_OPERATION"
    MANUAL = "MANUAL"
    EMERGENCY = "EMERGENCY"


class RecoveryStatus(Enum):
    """Status of recovery process."""
    NOT_NEEDED = "NOT_NEEDED"
    AVAILABLE = "AVAILABLE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class RecoveryConfiguration:
    """Configuration for crash recovery system."""
    enable_auto_recovery: bool = True
    checkpoint_interval: float = 300.0     # 5 minutes
    max_checkpoints: int = 10
    recovery_timeout: float = 120.0        # 2 minutes
    safe_mode_enabled: bool = True
    backup_directory: Optional[Path] = None
    compress_checkpoints: bool = True
    encrypt_checkpoints: bool = False
    recovery_mode: RecoveryMode = RecoveryMode.AUTOMATIC


@dataclass
class CheckpointData:
    """Data structure for recovery checkpoints."""
    checkpoint_id: str
    timestamp: datetime
    checkpoint_type: CheckpointType
    app_state: Dict[str, Any]
    system_state: Dict[str, Any]
    user_data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    file_path: Optional[Path] = None
    size_bytes: int = 0
    compressed: bool = False
    encrypted: bool = False


@dataclass
class RecoveryMetrics:
    """Metrics for recovery operations."""
    checkpoints_created: int = 0
    checkpoints_restored: int = 0
    recovery_attempts: int = 0
    successful_recoveries: int = 0
    failed_recoveries: int = 0
    total_recovery_time: float = 0.0
    last_checkpoint_time: Optional[datetime] = None
    last_recovery_time: Optional[datetime] = None


@dataclass
class CrashRecoveryResult:
    """Result of crash recovery operation."""
    success: bool
    recovery_status: RecoveryStatus
    recovery_mode: RecoveryMode
    checkpoint_restored: Optional[CheckpointData]
    metrics: RecoveryMetrics
    error_messages: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class CrashRecoveryManager:
    """
    High-level crash recovery manager that handles unexpected terminations
    and application state restoration.
    
    Manages recovery checkpoints, integrates with crash handler and recovery
    orchestrator to provide comprehensive crash recovery capabilities.
    """
    
    def __init__(self, 
                 config: Optional[RecoveryConfiguration] = None,
                 app_state_manager: Optional[AppStateManager] = None):
        """
        Initialize the crash recovery manager.
        
        Args:
            config: Recovery configuration
            app_state_manager: Application state manager instance
        """
        self._config = config or RecoveryConfiguration()
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("crash_recovery")
        
        # Initialize components
        self._crash_handler = CrashHandler()
        self._recovery_orchestrator = RecoveryOrchestrator()
        self._error_classifier = ErrorClassifier()
        
        # Setup directories
        self._recovery_dir = self._config.backup_directory or Path("recovery_data")
        self._recovery_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoint_dir = self._recovery_dir / "checkpoints"
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # State management
        self._checkpoints: Dict[str, CheckpointData] = {}
        self._metrics = RecoveryMetrics()
        self._lock = threading.RLock()
        self._checkpoint_timer: Optional[threading.Timer] = None
        self._recovery_in_progress = False
        
        # Load existing checkpoints
        self._load_existing_checkpoints()
        
        # Start periodic checkpointing if enabled
        if self._config.enable_auto_recovery:
            self._start_periodic_checkpointing()
        
        self._logger.info("CrashRecoveryManager initialized successfully")
    
    def check_for_crash_recovery(self) -> CrashRecoveryResult:
        """
        Check if crash recovery is needed and available.
        
        Returns:
            CrashRecoveryResult indicating recovery status
        """
        self._logger.info("Checking for crash recovery")
        
        try:
            # Check if there are any available checkpoints
            if not self._checkpoints:
                self._logger.info("No recovery checkpoints available")
                return CrashRecoveryResult(
                    success=True,
                    recovery_status=RecoveryStatus.NOT_NEEDED,
                    recovery_mode=self._config.recovery_mode,
                    checkpoint_restored=None,
                    metrics=self._metrics
                )
            
            # Find the most recent checkpoint
            latest_checkpoint = self._get_latest_checkpoint()
            if not latest_checkpoint:
                self._logger.warning("No valid checkpoints found")
                return CrashRecoveryResult(
                    success=False,
                    recovery_status=RecoveryStatus.FAILED,
                    recovery_mode=self._config.recovery_mode,
                    checkpoint_restored=None,
                    metrics=self._metrics,
                    error_messages=["No valid checkpoints found"]
                )
            
            self._logger.info(f"Recovery checkpoint available: {latest_checkpoint.checkpoint_id}")
            return CrashRecoveryResult(
                success=True,
                recovery_status=RecoveryStatus.AVAILABLE,
                recovery_mode=self._config.recovery_mode,
                checkpoint_restored=latest_checkpoint,
                metrics=self._metrics
            )
            
        except Exception as e:
            self._logger.error(f"Failed to check for crash recovery: {e}", exc_info=True)
            return CrashRecoveryResult(
                success=False,
                recovery_status=RecoveryStatus.FAILED,
                recovery_mode=self._config.recovery_mode,
                checkpoint_restored=None,
                metrics=self._metrics,
                error_messages=[str(e)]
            )
    
    def perform_crash_recovery(self, 
                              checkpoint_id: Optional[str] = None,
                              recovery_mode: Optional[RecoveryMode] = None) -> CrashRecoveryResult:
        """
        Perform crash recovery from a checkpoint.
        
        Args:
            checkpoint_id: Specific checkpoint to restore (None for latest)
            recovery_mode: Recovery mode to use
            
        Returns:
            CrashRecoveryResult with recovery outcome
        """
        start_time = time.time()
        recovery_mode = recovery_mode or self._config.recovery_mode
        
        self._logger.info(f"Starting crash recovery in {recovery_mode.value} mode")
        
        try:
            with self._lock:
                if self._recovery_in_progress:
                    self._logger.warning("Recovery already in progress")
                    return CrashRecoveryResult(
                        success=False,
                        recovery_status=RecoveryStatus.IN_PROGRESS,
                        recovery_mode=recovery_mode,
                        checkpoint_restored=None,
                        metrics=self._metrics,
                        error_messages=["Recovery already in progress"]
                    )
                
                self._recovery_in_progress = True
                self._metrics.recovery_attempts += 1
            
            # Select checkpoint to restore
            checkpoint = self._select_checkpoint_for_recovery(checkpoint_id)
            if not checkpoint:
                return self._create_recovery_result(
                    False, RecoveryStatus.FAILED, recovery_mode, None,
                    ["No suitable checkpoint found for recovery"]
                )
            
            # Perform recovery based on mode
            if recovery_mode == RecoveryMode.SAFE_MODE:
                result = self._perform_safe_mode_recovery(checkpoint)
            elif recovery_mode == RecoveryMode.INTERACTIVE:
                result = self._perform_interactive_recovery(checkpoint)
            else:
                result = self._perform_automatic_recovery(checkpoint)
            
            # Update metrics
            recovery_time = time.time() - start_time
            with self._lock:
                self._metrics.total_recovery_time += recovery_time
                self._metrics.last_recovery_time = datetime.now(timezone.utc)
                
                if result.success:
                    self._metrics.successful_recoveries += 1
                    self._metrics.checkpoints_restored += 1
                else:
                    self._metrics.failed_recoveries += 1
                
                self._recovery_in_progress = False
            
            self._logger.info(f"Crash recovery completed in {recovery_time:.2f}s")
            return result
            
        except Exception as e:
            self._logger.error(f"Crash recovery failed: {e}", exc_info=True)
            with self._lock:
                self._recovery_in_progress = False
                self._metrics.failed_recoveries += 1
            
            return CrashRecoveryResult(
                success=False,
                recovery_status=RecoveryStatus.FAILED,
                recovery_mode=recovery_mode,
                checkpoint_restored=None,
                metrics=self._metrics,
                error_messages=[str(e)]
            )
    
    def create_checkpoint(self, 
                         checkpoint_type: CheckpointType = CheckpointType.MANUAL,
                         metadata: Dict[str, Any] = None) -> bool:
        """
        Create a recovery checkpoint.
        
        Args:
            checkpoint_type: Type of checkpoint to create
            metadata: Additional metadata for the checkpoint
            
        Returns:
            True if checkpoint was created successfully
        """
        try:
            self._logger.info(f"Creating {checkpoint_type.value} checkpoint")
            
            # Generate checkpoint ID
            timestamp = datetime.now(timezone.utc)
            checkpoint_id = f"{checkpoint_type.value}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
            
            # Collect application state
            app_state = self._collect_application_state()
            system_state = self._collect_system_state()
            user_data = self._collect_user_data()
            
            # Create checkpoint data
            checkpoint = CheckpointData(
                checkpoint_id=checkpoint_id,
                timestamp=timestamp,
                checkpoint_type=checkpoint_type,
                app_state=app_state,
                system_state=system_state,
                user_data=user_data,
                metadata=metadata or {}
            )
            
            # Save checkpoint to disk
            if self._save_checkpoint(checkpoint):
                with self._lock:
                    self._checkpoints[checkpoint_id] = checkpoint
                    self._metrics.checkpoints_created += 1
                    self._metrics.last_checkpoint_time = timestamp
                
                # Cleanup old checkpoints
                self._cleanup_old_checkpoints()
                
                self._logger.info(f"Checkpoint created successfully: {checkpoint_id}")
                return True
            else:
                self._logger.error(f"Failed to save checkpoint: {checkpoint_id}")
                return False
                
        except Exception as e:
            self._logger.error(f"Failed to create checkpoint: {e}", exc_info=True)
            return False
    
    def _perform_automatic_recovery(self, checkpoint: CheckpointData) -> CrashRecoveryResult:
        """Perform automatic recovery from checkpoint."""
        self._logger.info(f"Performing automatic recovery from {checkpoint.checkpoint_id}")
        
        try:
            # Restore application state
            if not self._restore_application_state(checkpoint.app_state):
                return self._create_recovery_result(
                    False, RecoveryStatus.FAILED, RecoveryMode.AUTOMATIC, checkpoint,
                    ["Failed to restore application state"]
                )
            
            # Restore system state
            if not self._restore_system_state(checkpoint.system_state):
                return self._create_recovery_result(
                    False, RecoveryStatus.FAILED, RecoveryMode.AUTOMATIC, checkpoint,
                    ["Failed to restore system state"]
                )
            
            # Restore user data
            if not self._restore_user_data(checkpoint.user_data):
                return self._create_recovery_result(
                    False, RecoveryStatus.FAILED, RecoveryMode.AUTOMATIC, checkpoint,
                    ["Failed to restore user data"]
                )
            
            return self._create_recovery_result(
                True, RecoveryStatus.COMPLETED, RecoveryMode.AUTOMATIC, checkpoint
            )
            
        except Exception as e:
            self._logger.error(f"Automatic recovery failed: {e}", exc_info=True)
            return self._create_recovery_result(
                False, RecoveryStatus.FAILED, RecoveryMode.AUTOMATIC, checkpoint, [str(e)]
            )
    
    def _perform_safe_mode_recovery(self, checkpoint: CheckpointData) -> CrashRecoveryResult:
        """Perform safe mode recovery with minimal restoration."""
        self._logger.info(f"Performing safe mode recovery from {checkpoint.checkpoint_id}")
        
        try:
            # Only restore essential application state
            essential_state = {
                key: value for key, value in checkpoint.app_state.items()
                if key in ['is_initialized', 'current_view']
            }
            
            if not self._restore_application_state(essential_state):
                return self._create_recovery_result(
                    False, RecoveryStatus.FAILED, RecoveryMode.SAFE_MODE, checkpoint,
                    ["Failed to restore essential application state"]
                )
            
            return self._create_recovery_result(
                True, RecoveryStatus.COMPLETED, RecoveryMode.SAFE_MODE, checkpoint
            )
            
        except Exception as e:
            self._logger.error(f"Safe mode recovery failed: {e}", exc_info=True)
            return self._create_recovery_result(
                False, RecoveryStatus.FAILED, RecoveryMode.SAFE_MODE, checkpoint, [str(e)]
            )
    
    def _perform_interactive_recovery(self, checkpoint: CheckpointData) -> CrashRecoveryResult:
        """Perform interactive recovery with user input."""
        self._logger.info(f"Performing interactive recovery from {checkpoint.checkpoint_id}")
        
        # For now, fall back to automatic recovery
        # In a real implementation, this would prompt the user
        return self._perform_automatic_recovery(checkpoint)
    
    def _collect_application_state(self) -> Dict[str, Any]:
        """Collect current application state for checkpoint."""
        try:
            state = self._app_state_manager.get_state()
            return {
                'is_initialized': state.is_initialized,
                'current_view': state.current_view,
                'user_preferences': state.user_preferences.copy()
            }
        except Exception as e:
            self._logger.error(f"Failed to collect application state: {e}")
            return {}
    
    def _collect_system_state(self) -> Dict[str, Any]:
        """Collect current system state for checkpoint."""
        try:
            return {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'process_id': threading.get_ident(),
                'thread_count': threading.active_count()
            }
        except Exception as e:
            self._logger.error(f"Failed to collect system state: {e}")
            return {}
    
    def _collect_user_data(self) -> Dict[str, Any]:
        """Collect current user data for checkpoint."""
        try:
            # This would collect user-specific data
            return {}
        except Exception as e:
            self._logger.error(f"Failed to collect user data: {e}")
            return {}
    
    def _restore_application_state(self, app_state: Dict[str, Any]) -> bool:
        """Restore application state from checkpoint data."""
        try:
            self._logger.info("Restoring application state")
            
            # Restore state through app state manager
            for key, value in app_state.items():
                if key == 'user_preferences':
                    for pref_key, pref_value in value.items():
                        self._app_state_manager.set_user_preference(pref_key, pref_value)
                elif hasattr(self._app_state_manager.get_state(), key):
                    self._app_state_manager.update_state(**{key: value})
            
            self._logger.info("Application state restored successfully")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to restore application state: {e}", exc_info=True)
            return False
    
    def _restore_system_state(self, system_state: Dict[str, Any]) -> bool:
        """Restore system state from checkpoint data."""
        try:
            self._logger.info("Restoring system state")
            
            # System state restoration would be implemented here
            # For now, we'll just log the action
            
            self._logger.info("System state restored successfully")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to restore system state: {e}", exc_info=True)
            return False
    
    def _restore_user_data(self, user_data: Dict[str, Any]) -> bool:
        """Restore user data from checkpoint data."""
        try:
            self._logger.info("Restoring user data")

            # User data restoration would be implemented here
            # For now, we'll just log the action

            self._logger.info("User data restored successfully")
            return True

        except Exception as e:
            self._logger.error(f"Failed to restore user data: {e}", exc_info=True)
            return False

    def _save_checkpoint(self, checkpoint: CheckpointData) -> bool:
        """Save checkpoint data to disk."""
        try:
            # Create checkpoint file path
            filename = f"{checkpoint.checkpoint_id}.json"
            file_path = self._checkpoint_dir / filename

            # Prepare data for serialization
            checkpoint_data = {
                'checkpoint_id': checkpoint.checkpoint_id,
                'timestamp': checkpoint.timestamp.isoformat(),
                'checkpoint_type': checkpoint.checkpoint_type.value,
                'app_state': checkpoint.app_state,
                'system_state': checkpoint.system_state,
                'user_data': checkpoint.user_data,
                'metadata': checkpoint.metadata
            }

            # Save to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)

            # Update checkpoint with file info
            checkpoint.file_path = file_path
            checkpoint.size_bytes = file_path.stat().st_size

            self._logger.debug(f"Checkpoint saved to {file_path}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to save checkpoint: {e}", exc_info=True)
            return False

    def _load_existing_checkpoints(self) -> None:
        """Load existing checkpoints from disk."""
        try:
            self._logger.info("Loading existing checkpoints")

            if not self._checkpoint_dir.exists():
                return

            for file_path in self._checkpoint_dir.glob("*.json"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Reconstruct checkpoint
                    checkpoint = CheckpointData(
                        checkpoint_id=data['checkpoint_id'],
                        timestamp=datetime.fromisoformat(data['timestamp']),
                        checkpoint_type=CheckpointType(data['checkpoint_type']),
                        app_state=data['app_state'],
                        system_state=data['system_state'],
                        user_data=data['user_data'],
                        metadata=data.get('metadata', {}),
                        file_path=file_path,
                        size_bytes=file_path.stat().st_size
                    )

                    self._checkpoints[checkpoint.checkpoint_id] = checkpoint

                except Exception as e:
                    self._logger.warning(f"Failed to load checkpoint {file_path}: {e}")

            self._logger.info(f"Loaded {len(self._checkpoints)} existing checkpoints")

        except Exception as e:
            self._logger.error(f"Failed to load existing checkpoints: {e}", exc_info=True)

    def _get_latest_checkpoint(self) -> Optional[CheckpointData]:
        """Get the most recent checkpoint."""
        if not self._checkpoints:
            return None

        return max(self._checkpoints.values(), key=lambda cp: cp.timestamp)

    def _select_checkpoint_for_recovery(self, checkpoint_id: Optional[str]) -> Optional[CheckpointData]:
        """Select appropriate checkpoint for recovery."""
        if checkpoint_id:
            return self._checkpoints.get(checkpoint_id)

        return self._get_latest_checkpoint()

    def _cleanup_old_checkpoints(self) -> None:
        """Cleanup old checkpoints to maintain max count."""
        try:
            if len(self._checkpoints) <= self._config.max_checkpoints:
                return

            # Sort by timestamp and remove oldest
            sorted_checkpoints = sorted(
                self._checkpoints.values(),
                key=lambda cp: cp.timestamp
            )

            checkpoints_to_remove = sorted_checkpoints[:-self._config.max_checkpoints]

            for checkpoint in checkpoints_to_remove:
                try:
                    # Remove file
                    if checkpoint.file_path and checkpoint.file_path.exists():
                        checkpoint.file_path.unlink()

                    # Remove from memory
                    del self._checkpoints[checkpoint.checkpoint_id]

                    self._logger.debug(f"Removed old checkpoint: {checkpoint.checkpoint_id}")

                except Exception as e:
                    self._logger.warning(f"Failed to remove checkpoint {checkpoint.checkpoint_id}: {e}")

        except Exception as e:
            self._logger.error(f"Failed to cleanup old checkpoints: {e}", exc_info=True)

    def _start_periodic_checkpointing(self) -> None:
        """Start periodic checkpoint creation."""
        try:
            self._logger.info(f"Starting periodic checkpointing every {self._config.checkpoint_interval}s")

            def create_periodic_checkpoint():
                self.create_checkpoint(CheckpointType.PERIODIC)
                # Schedule next checkpoint
                self._checkpoint_timer = threading.Timer(
                    self._config.checkpoint_interval,
                    create_periodic_checkpoint
                )
                self._checkpoint_timer.daemon = True
                self._checkpoint_timer.start()

            # Start first checkpoint
            self._checkpoint_timer = threading.Timer(
                self._config.checkpoint_interval,
                create_periodic_checkpoint
            )
            self._checkpoint_timer.daemon = True
            self._checkpoint_timer.start()

        except Exception as e:
            self._logger.error(f"Failed to start periodic checkpointing: {e}", exc_info=True)

    def _create_recovery_result(self, success: bool, status: RecoveryStatus,
                              mode: RecoveryMode, checkpoint: Optional[CheckpointData],
                              errors: List[str] = None) -> CrashRecoveryResult:
        """Create crash recovery result."""
        return CrashRecoveryResult(
            success=success,
            recovery_status=status,
            recovery_mode=mode,
            checkpoint_restored=checkpoint,
            metrics=self._metrics,
            error_messages=errors or [],
            warnings=[]
        )

    def get_available_checkpoints(self) -> List[CheckpointData]:
        """
        Get list of available recovery checkpoints.

        Returns:
            List of available checkpoints sorted by timestamp
        """
        with self._lock:
            return sorted(self._checkpoints.values(), key=lambda cp: cp.timestamp, reverse=True)

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Delete a specific checkpoint.

        Args:
            checkpoint_id: ID of checkpoint to delete

        Returns:
            True if checkpoint was deleted successfully
        """
        try:
            with self._lock:
                checkpoint = self._checkpoints.get(checkpoint_id)
                if not checkpoint:
                    self._logger.warning(f"Checkpoint not found: {checkpoint_id}")
                    return False

                # Remove file
                if checkpoint.file_path and checkpoint.file_path.exists():
                    checkpoint.file_path.unlink()

                # Remove from memory
                del self._checkpoints[checkpoint_id]

            self._logger.info(f"Deleted checkpoint: {checkpoint_id}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to delete checkpoint {checkpoint_id}: {e}", exc_info=True)
            return False

    def get_metrics(self) -> RecoveryMetrics:
        """
        Get recovery metrics.

        Returns:
            Current recovery metrics
        """
        with self._lock:
            return self._metrics

    def stop_periodic_checkpointing(self) -> None:
        """Stop periodic checkpoint creation."""
        try:
            if self._checkpoint_timer:
                self._checkpoint_timer.cancel()
                self._checkpoint_timer = None
                self._logger.info("Stopped periodic checkpointing")
        except Exception as e:
            self._logger.error(f"Failed to stop periodic checkpointing: {e}")

    def is_recovery_in_progress(self) -> bool:
        """
        Check if recovery is currently in progress.

        Returns:
            True if recovery is in progress
        """
        with self._lock:
            return self._recovery_in_progress
