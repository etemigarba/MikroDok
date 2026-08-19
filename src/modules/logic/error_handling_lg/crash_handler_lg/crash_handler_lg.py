"""
Module: crash_handler_lg
Description: Handles application crashes with state preservation and recovery
Phase: 1
Location: /src/modules/logic/error_handling_lg/crash_handler_lg/
"""

# Standard library imports
import sys
import os
import signal
import traceback
import pickle
import json
import time
from typing import Dict, Any, Optional, List, Callable, Union
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
import threading
import atexit
import psutil

# Third-party imports
# None required for this module

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager


class CrashType(Enum):
    """Types of application crashes."""
    UNHANDLED_EXCEPTION = "UNHANDLED_EXCEPTION"
    MEMORY_EXHAUSTION = "MEMORY_EXHAUSTION"
    SYSTEM_SIGNAL = "SYSTEM_SIGNAL"
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
    TRAINING_FAILURE = "TRAINING_FAILURE"
    GPU_ERROR = "GPU_ERROR"
    DISK_FULL = "DISK_FULL"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    USER_TERMINATION = "USER_TERMINATION"
    UNKNOWN = "UNKNOWN"


@dataclass
class CrashContext:
    """Context information for crash handling."""
    crash_id: str
    crash_type: CrashType
    timestamp: datetime
    process_id: int
    thread_id: int
    exception_info: Optional[str] = None
    stack_trace: Optional[str] = None
    system_state: Dict[str, Any] = field(default_factory=dict)
    memory_usage: Dict[str, Any] = field(default_factory=dict)
    active_sessions: List[str] = field(default_factory=list)
    recovery_hints: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert crash context to dictionary."""
        return {
            'crash_id': self.crash_id,
            'crash_type': self.crash_type.value,
            'timestamp': self.timestamp.isoformat(),
            'process_id': self.process_id,
            'thread_id': self.thread_id,
            'exception_info': self.exception_info,
            'stack_trace': self.stack_trace,
            'system_state': self.system_state,
            'memory_usage': self.memory_usage,
            'active_sessions': self.active_sessions,
            'recovery_hints': self.recovery_hints
        }


@dataclass
class RecoveryPoint:
    """Recovery point for crash recovery."""
    recovery_id: str
    timestamp: datetime
    application_state: Dict[str, Any]
    session_states: Dict[str, Any] = field(default_factory=dict)
    checkpoint_paths: List[str] = field(default_factory=list)
    configuration: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert recovery point to dictionary."""
        return {
            'recovery_id': self.recovery_id,
            'timestamp': self.timestamp.isoformat(),
            'application_state': self.application_state,
            'session_states': self.session_states,
            'checkpoint_paths': self.checkpoint_paths,
            'configuration': self.configuration,
            'metadata': self.metadata
        }


class CrashHandler:
    """
    Handles application crashes with state preservation and recovery.
    
    This class manages crash detection, state snapshots, recovery point creation,
    and automatic restart procedures to ensure data integrity and system resilience.
    """
    
    def __init__(self, crash_dir: Optional[Path] = None):
        """
        Initialize the crash handler.
        
        Args:
            crash_dir: Directory for storing crash data and recovery points
        """
        self._log_manager = get_log_manager()
        self._logger = self._log_manager.get_logger("crash_handler")
        self._app_state = AppStateManager()
        
        # Configuration
        self._crash_dir = crash_dir or Path("crash_data")
        self._crash_dir.mkdir(parents=True, exist_ok=True)
        self._recovery_dir = self._crash_dir / "recovery_points"
        self._recovery_dir.mkdir(parents=True, exist_ok=True)
        
        # State management
        self._crash_handlers: Dict[CrashType, Callable] = {}
        self._recovery_points: List[RecoveryPoint] = []
        self._crash_history: List[CrashContext] = []
        self._lock = threading.RLock()
        self._is_handling_crash = False
        
        # Configuration
        self._max_recovery_points = 10
        self._max_crash_history = 100
        self._auto_recovery_enabled = True
        self._recovery_timeout = 30  # seconds
        
        # Initialize crash handling
        self._initialize_crash_handlers()
        self._register_signal_handlers()
        self._register_exit_handler()
        
        # Load existing recovery points
        self._load_recovery_points()
        
        self._logger.info("CrashHandler initialized successfully")
    
    def handle_crash(self, exception: Optional[Exception] = None, 
                    crash_type: Optional[CrashType] = None,
                    context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Handle application crash with state preservation.
        
        Args:
            exception: Exception that caused the crash
            crash_type: Type of crash that occurred
            context: Additional context information
            
        Returns:
            bool: True if crash was handled successfully
        """
        if self._is_handling_crash:
            # Prevent recursive crash handling
            return False
        
        self._is_handling_crash = True
        
        try:
            # Create crash context
            crash_context = self._create_crash_context(exception, crash_type, context or {})
            
            # Log crash occurrence
            self._logger.critical(f"Application crash detected: {crash_context.crash_type.value}")
            
            # Create recovery point before handling
            recovery_point = self._create_recovery_point(crash_context)
            
            # Save crash information
            self._save_crash_data(crash_context)
            
            # Execute crash-specific handler
            handler = self._crash_handlers.get(crash_context.crash_type)
            if handler:
                handler(crash_context, recovery_point)
            else:
                self._handle_generic_crash(crash_context, recovery_point)
            
            # Update crash history
            with self._lock:
                self._crash_history.append(crash_context)
                if len(self._crash_history) > self._max_crash_history:
                    self._crash_history.pop(0)
            
            self._logger.info(f"Crash handled successfully: {crash_context.crash_id}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to handle crash: {e}")
            return False
        finally:
            self._is_handling_crash = False
    
    def create_recovery_point(self, name: Optional[str] = None) -> RecoveryPoint:
        """
        Create a recovery point for the current application state.
        
        Args:
            name: Optional name for the recovery point
            
        Returns:
            RecoveryPoint: Created recovery point
        """
        try:
            recovery_id = f"recovery_{int(datetime.now().timestamp() * 1000)}"
            if name:
                recovery_id = f"{recovery_id}_{name}"
            
            # Capture current application state
            app_state = self._capture_application_state()
            session_states = self._capture_session_states()
            checkpoint_paths = self._get_checkpoint_paths()
            configuration = self._capture_configuration()
            
            recovery_point = RecoveryPoint(
                recovery_id=recovery_id,
                timestamp=datetime.now(timezone.utc),
                application_state=app_state,
                session_states=session_states,
                checkpoint_paths=checkpoint_paths,
                configuration=configuration,
                metadata={
                    'created_by': 'manual',
                    'memory_usage': self._get_memory_usage(),
                    'active_threads': threading.active_count()
                }
            )
            
            # Save recovery point
            self._save_recovery_point(recovery_point)
            
            # Add to recovery points list
            with self._lock:
                self._recovery_points.append(recovery_point)
                if len(self._recovery_points) > self._max_recovery_points:
                    oldest_point = self._recovery_points.pop(0)
                    self._cleanup_recovery_point(oldest_point)
            
            self._logger.info(f"Recovery point created: {recovery_id}")
            return recovery_point
            
        except Exception as e:
            self._logger.error(f"Failed to create recovery point: {e}")
            raise
    
    def restore_from_recovery_point(self, recovery_id: str) -> bool:
        """
        Restore application state from a recovery point.
        
        Args:
            recovery_id: ID of the recovery point to restore from
            
        Returns:
            bool: True if restoration was successful
        """
        try:
            # Find recovery point
            recovery_point = None
            with self._lock:
                for point in self._recovery_points:
                    if point.recovery_id == recovery_id:
                        recovery_point = point
                        break
            
            if not recovery_point:
                self._logger.error(f"Recovery point not found: {recovery_id}")
                return False
            
            # Restore application state
            success = self._restore_application_state(recovery_point)
            
            if success:
                self._logger.info(f"Successfully restored from recovery point: {recovery_id}")
            else:
                self._logger.error(f"Failed to restore from recovery point: {recovery_id}")
            
            return success
            
        except Exception as e:
            self._logger.error(f"Recovery point restoration failed: {e}")
            return False

    def _create_crash_context(self, exception: Optional[Exception],
                            crash_type: Optional[CrashType],
                            context: Dict[str, Any]) -> CrashContext:
        """Create crash context from exception and additional information."""
        # Determine crash type
        if crash_type is None:
            crash_type = self._determine_crash_type(exception)

        crash_id = f"crash_{int(datetime.now().timestamp() * 1000)}"

        return CrashContext(
            crash_id=crash_id,
            crash_type=crash_type,
            timestamp=datetime.now(timezone.utc),
            process_id=os.getpid(),
            thread_id=threading.get_ident(),
            exception_info=str(exception) if exception else None,
            stack_trace=traceback.format_exc() if exception else None,
            system_state=self._capture_system_state(),
            memory_usage=self._get_memory_usage(),
            active_sessions=context.get('active_sessions', []),
            recovery_hints=context.get('recovery_hints', {})
        )

    def _determine_crash_type(self, exception: Optional[Exception]) -> CrashType:
        """Determine crash type from exception."""
        if not exception:
            return CrashType.UNKNOWN

        exception_name = type(exception).__name__.lower()
        exception_message = str(exception).lower()

        if 'memory' in exception_name or 'memory' in exception_message:
            return CrashType.MEMORY_EXHAUSTION
        elif 'cuda' in exception_message or 'gpu' in exception_message:
            return CrashType.GPU_ERROR
        elif 'disk' in exception_message or 'space' in exception_message:
            return CrashType.DISK_FULL
        elif 'training' in exception_message:
            return CrashType.TRAINING_FAILURE
        elif 'network' in exception_message or 'connection' in exception_message:
            return CrashType.NETWORK_FAILURE
        else:
            return CrashType.UNHANDLED_EXCEPTION

    def _create_recovery_point(self, crash_context: CrashContext) -> RecoveryPoint:
        """Create recovery point for crash context."""
        recovery_id = f"crash_recovery_{crash_context.crash_id}"

        return RecoveryPoint(
            recovery_id=recovery_id,
            timestamp=crash_context.timestamp,
            application_state=self._capture_application_state(),
            session_states=self._capture_session_states(),
            checkpoint_paths=self._get_checkpoint_paths(),
            configuration=self._capture_configuration(),
            metadata={
                'created_by': 'crash_handler',
                'crash_id': crash_context.crash_id,
                'crash_type': crash_context.crash_type.value
            }
        )

    def _capture_application_state(self) -> Dict[str, Any]:
        """Capture current application state."""
        try:
            return {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'app_version': '1.0.0',  # This would come from app configuration
                'active_modules': self._get_active_modules(),
                'configuration': self._capture_configuration(),
                'runtime_state': {
                    'uptime': time.time() - self._start_time if hasattr(self, '_start_time') else 0,
                    'memory_usage': self._get_memory_usage(),
                    'thread_count': threading.active_count()
                }
            }
        except Exception as e:
            self._logger.error(f"Failed to capture application state: {e}")
            return {}

    def _capture_session_states(self) -> Dict[str, Any]:
        """Capture states of active sessions."""
        try:
            # This would interact with session management system
            return {
                'active_sessions': [],
                'training_sessions': [],
                'chat_sessions': []
            }
        except Exception as e:
            self._logger.error(f"Failed to capture session states: {e}")
            return {}

    def _get_checkpoint_paths(self) -> List[str]:
        """Get paths to available checkpoints."""
        try:
            checkpoint_dirs = [
                Path("checkpoints"),
                Path("models/checkpoints"),
                Path("training/checkpoints")
            ]

            checkpoint_paths = []
            for checkpoint_dir in checkpoint_dirs:
                if checkpoint_dir.exists():
                    checkpoint_paths.extend([
                        str(p) for p in checkpoint_dir.glob("**/*.json")
                    ])

            return checkpoint_paths
        except Exception as e:
            self._logger.error(f"Failed to get checkpoint paths: {e}")
            return []

    def _capture_configuration(self) -> Dict[str, Any]:
        """Capture current application configuration."""
        try:
            # This would capture actual configuration
            return {
                'logging_level': 'INFO',
                'crash_handling_enabled': True,
                'auto_recovery_enabled': self._auto_recovery_enabled,
                'max_recovery_points': self._max_recovery_points
            }
        except Exception as e:
            self._logger.error(f"Failed to capture configuration: {e}")
            return {}

    def _capture_system_state(self) -> Dict[str, Any]:
        """Capture current system state."""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage': {
                    'total': psutil.disk_usage('/').total,
                    'used': psutil.disk_usage('/').used,
                    'free': psutil.disk_usage('/').free
                },
                'process_count': len(psutil.pids()),
                'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
            }
        except Exception as e:
            self._logger.error(f"Failed to capture system state: {e}")
            return {}

    def _get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage information."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()

            return {
                'rss': memory_info.rss,
                'vms': memory_info.vms,
                'percent': process.memory_percent(),
                'available': psutil.virtual_memory().available,
                'total': psutil.virtual_memory().total
            }
        except Exception as e:
            self._logger.error(f"Failed to get memory usage: {e}")
            return {}

    def _get_active_modules(self) -> List[str]:
        """Get list of active modules."""
        try:
            return list(sys.modules.keys())
        except Exception as e:
            self._logger.error(f"Failed to get active modules: {e}")
            return []

    def _save_crash_data(self, crash_context: CrashContext) -> None:
        """Save crash data to disk."""
        try:
            crash_file = self._crash_dir / f"{crash_context.crash_id}.json"
            with open(crash_file, 'w') as f:
                json.dump(crash_context.to_dict(), f, indent=2)

            self._logger.info(f"Crash data saved: {crash_file}")

        except Exception as e:
            self._logger.error(f"Failed to save crash data: {e}")

    def _save_recovery_point(self, recovery_point: RecoveryPoint) -> None:
        """Save recovery point to disk."""
        try:
            recovery_file = self._recovery_dir / f"{recovery_point.recovery_id}.json"
            with open(recovery_file, 'w') as f:
                json.dump(recovery_point.to_dict(), f, indent=2)

            self._logger.info(f"Recovery point saved: {recovery_file}")

        except Exception as e:
            self._logger.error(f"Failed to save recovery point: {e}")

    def _load_recovery_points(self) -> None:
        """Load existing recovery points from disk."""
        try:
            recovery_files = list(self._recovery_dir.glob("*.json"))

            for recovery_file in recovery_files:
                try:
                    with open(recovery_file, 'r') as f:
                        data = json.load(f)

                    recovery_point = RecoveryPoint(
                        recovery_id=data['recovery_id'],
                        timestamp=datetime.fromisoformat(data['timestamp']),
                        application_state=data['application_state'],
                        session_states=data.get('session_states', {}),
                        checkpoint_paths=data.get('checkpoint_paths', []),
                        configuration=data.get('configuration', {}),
                        metadata=data.get('metadata', {})
                    )

                    self._recovery_points.append(recovery_point)

                except Exception as e:
                    self._logger.error(f"Failed to load recovery point {recovery_file}: {e}")

            # Sort by timestamp
            self._recovery_points.sort(key=lambda p: p.timestamp, reverse=True)

            # Limit to max recovery points
            if len(self._recovery_points) > self._max_recovery_points:
                excess_points = self._recovery_points[self._max_recovery_points:]
                self._recovery_points = self._recovery_points[:self._max_recovery_points]

                # Clean up excess recovery points
                for point in excess_points:
                    self._cleanup_recovery_point(point)

            self._logger.info(f"Loaded {len(self._recovery_points)} recovery points")

        except Exception as e:
            self._logger.error(f"Failed to load recovery points: {e}")

    def _cleanup_recovery_point(self, recovery_point: RecoveryPoint) -> None:
        """Clean up recovery point files."""
        try:
            recovery_file = self._recovery_dir / f"{recovery_point.recovery_id}.json"
            if recovery_file.exists():
                recovery_file.unlink()

            self._logger.debug(f"Cleaned up recovery point: {recovery_point.recovery_id}")

        except Exception as e:
            self._logger.error(f"Failed to cleanup recovery point: {e}")

    def _restore_application_state(self, recovery_point: RecoveryPoint) -> bool:
        """Restore application state from recovery point."""
        try:
            # This would interact with actual application components
            self._logger.info(f"Restoring application state from: {recovery_point.recovery_id}")

            # Simulate restoration process
            time.sleep(0.1)

            return True

        except Exception as e:
            self._logger.error(f"Failed to restore application state: {e}")
            return False

    def _initialize_crash_handlers(self) -> None:
        """Initialize crash type specific handlers."""
        self._crash_handlers = {
            CrashType.MEMORY_EXHAUSTION: self._handle_memory_exhaustion,
            CrashType.GPU_ERROR: self._handle_gpu_error,
            CrashType.TRAINING_FAILURE: self._handle_training_failure,
            CrashType.DISK_FULL: self._handle_disk_full,
            CrashType.SYSTEM_SIGNAL: self._handle_system_signal,
            CrashType.UNHANDLED_EXCEPTION: self._handle_generic_crash
        }

    def _register_signal_handlers(self) -> None:
        """Register system signal handlers."""
        try:
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
            if hasattr(signal, 'SIGHUP'):
                signal.signal(signal.SIGHUP, self._signal_handler)

            self._logger.debug("Signal handlers registered")

        except Exception as e:
            self._logger.error(f"Failed to register signal handlers: {e}")

    def _register_exit_handler(self) -> None:
        """Register exit handler for cleanup."""
        atexit.register(self._exit_handler)

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle system signals."""
        signal_name = signal.Signals(signum).name
        self._logger.warning(f"Received signal: {signal_name}")

        # Handle crash with signal context
        self.handle_crash(
            exception=None,
            crash_type=CrashType.SYSTEM_SIGNAL,
            context={
                'signal_number': signum,
                'signal_name': signal_name,
                'frame_info': str(frame) if frame else None
            }
        )

    def _exit_handler(self) -> None:
        """Handle application exit."""
        self._logger.info("Application exit handler called")

        # Create final recovery point
        try:
            self.create_recovery_point("exit_point")
        except Exception as e:
            self._logger.error(f"Failed to create exit recovery point: {e}")

    def _handle_memory_exhaustion(self, crash_context: CrashContext,
                                recovery_point: RecoveryPoint) -> None:
        """Handle memory exhaustion crashes."""
        self._logger.critical("Handling memory exhaustion crash")

        # Attempt to free memory
        try:
            # This would interact with memory management system
            self._logger.info("Attempting memory cleanup")
        except Exception as e:
            self._logger.error(f"Memory cleanup failed: {e}")

    def _handle_gpu_error(self, crash_context: CrashContext,
                        recovery_point: RecoveryPoint) -> None:
        """Handle GPU-related crashes."""
        self._logger.critical("Handling GPU error crash")

        # Reset GPU state if possible
        try:
            self._logger.info("Attempting GPU state reset")
        except Exception as e:
            self._logger.error(f"GPU reset failed: {e}")

    def _handle_training_failure(self, crash_context: CrashContext,
                               recovery_point: RecoveryPoint) -> None:
        """Handle training failure crashes."""
        self._logger.critical("Handling training failure crash")

        # Save training state
        try:
            self._logger.info("Saving training state for recovery")
        except Exception as e:
            self._logger.error(f"Training state save failed: {e}")

    def _handle_disk_full(self, crash_context: CrashContext,
                        recovery_point: RecoveryPoint) -> None:
        """Handle disk full crashes."""
        self._logger.critical("Handling disk full crash")

        # Attempt to free disk space
        try:
            self._logger.info("Attempting disk cleanup")
        except Exception as e:
            self._logger.error(f"Disk cleanup failed: {e}")

    def _handle_system_signal(self, crash_context: CrashContext,
                            recovery_point: RecoveryPoint) -> None:
        """Handle system signal crashes."""
        self._logger.critical("Handling system signal crash")

        # Graceful shutdown
        try:
            self._logger.info("Initiating graceful shutdown")
        except Exception as e:
            self._logger.error(f"Graceful shutdown failed: {e}")

    def _handle_generic_crash(self, crash_context: CrashContext,
                            recovery_point: RecoveryPoint) -> None:
        """Handle generic crashes."""
        self._logger.critical("Handling generic crash")

        # Generic crash handling
        try:
            self._logger.info("Performing generic crash recovery")
        except Exception as e:
            self._logger.error(f"Generic crash recovery failed: {e}")

    def get_crash_stats(self) -> Dict[str, Any]:
        """Get crash handling statistics."""
        with self._lock:
            return {
                'total_crashes': len(self._crash_history),
                'recovery_points': len(self._recovery_points),
                'crash_types': self._get_crash_type_distribution(),
                'auto_recovery_enabled': self._auto_recovery_enabled,
                'last_crash': self._crash_history[-1].to_dict() if self._crash_history else None
            }

    def _get_crash_type_distribution(self) -> Dict[str, int]:
        """Get distribution of crash types."""
        distribution = {}
        for crash in self._crash_history:
            crash_type = crash.crash_type.value
            distribution[crash_type] = distribution.get(crash_type, 0) + 1
        return distribution

    def get_recovery_points(self) -> List[Dict[str, Any]]:
        """Get list of available recovery points."""
        with self._lock:
            return [point.to_dict() for point in self._recovery_points]

    def cleanup_old_data(self, days_old: int = 7) -> None:
        """Clean up old crash data and recovery points."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)

        # Clean up old crash files
        try:
            crash_files = list(self._crash_dir.glob("crash_*.json"))
            for crash_file in crash_files:
                if datetime.fromtimestamp(crash_file.stat().st_mtime, tz=timezone.utc) < cutoff_date:
                    crash_file.unlink()
                    self._logger.debug(f"Cleaned up old crash file: {crash_file}")
        except Exception as e:
            self._logger.error(f"Failed to cleanup old crash files: {e}")

        # Clean up old recovery points
        with self._lock:
            old_points = [p for p in self._recovery_points if p.timestamp < cutoff_date]
            for point in old_points:
                self._recovery_points.remove(point)
                self._cleanup_recovery_point(point)
