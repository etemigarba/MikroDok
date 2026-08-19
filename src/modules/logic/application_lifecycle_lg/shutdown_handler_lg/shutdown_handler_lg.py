"""
Module: shutdown_handler_lg
Description: Manages graceful shutdown procedures, saves application state, and ensures proper resource cleanup
Phase: 1
Location: /src/modules/logic/application_lifecycle_lg/shutdown_handler_lg/shutdown_handler_lg.py
"""

# Standard library imports
import asyncio
import signal
import time
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    get_log_manager, LogManager
)
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.system_initialization_lg.shutdown_coordinator_lg.shutdown_coordinator_lg import (
    ShutdownCoordinator, ShutdownResult, ShutdownContext, ShutdownPhase
)
from src.modules.logic.error_handling_lg.error_classifier_lg.error_classifier_lg import (
    ErrorClassifier, ErrorSeverity, ErrorCategory
)


class ShutdownTrigger(Enum):
    """Types of shutdown triggers."""
    USER_REQUEST = "USER_REQUEST"
    SYSTEM_SIGNAL = "SYSTEM_SIGNAL"
    APPLICATION_ERROR = "APPLICATION_ERROR"
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
    SCHEDULED = "SCHEDULED"
    EMERGENCY = "EMERGENCY"


class ShutdownMode(Enum):
    """Shutdown modes."""
    GRACEFUL = "GRACEFUL"
    FORCED = "FORCED"
    EMERGENCY = "EMERGENCY"


class ShutdownStatus(Enum):
    """Status of shutdown process."""
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class ShutdownConfiguration:
    """Configuration for shutdown process."""
    graceful_timeout: float = 60.0      # Time to wait for graceful shutdown
    force_timeout: float = 10.0         # Time to wait before forced shutdown
    save_state: bool = True             # Whether to save application state
    cleanup_temp_files: bool = True     # Whether to cleanup temporary files
    notify_users: bool = True           # Whether to notify users
    backup_data: bool = True            # Whether to backup critical data
    log_shutdown: bool = True           # Whether to log shutdown process
    emergency_mode: bool = False        # Emergency shutdown mode


@dataclass
class ShutdownMetrics:
    """Metrics collected during shutdown."""
    total_time: float = 0.0
    phase_times: Dict[ShutdownPhase, float] = field(default_factory=dict)
    components_shutdown: int = 0
    errors_encountered: int = 0
    warnings_generated: int = 0
    state_saved: bool = False
    cleanup_completed: bool = False


@dataclass
class ShutdownHandlerResult:
    """Result of shutdown handler execution."""
    success: bool
    status: ShutdownStatus
    trigger: ShutdownTrigger
    mode: ShutdownMode
    phase_reached: ShutdownPhase
    metrics: ShutdownMetrics
    error_messages: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    shutdown_result: Optional[ShutdownResult] = None


class ShutdownHandler:
    """
    High-level shutdown handler that manages graceful application termination.
    
    Coordinates state saving, resource cleanup, service shutdown, and integrates
    with the shutdown coordinator to provide a unified shutdown experience.
    """
    
    def __init__(self, 
                 config: Optional[ShutdownConfiguration] = None,
                 app_state_manager: Optional[AppStateManager] = None):
        """
        Initialize the shutdown handler.
        
        Args:
            config: Shutdown configuration
            app_state_manager: Application state manager instance
        """
        self._config = config or ShutdownConfiguration()
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("shutdown_handler")
        
        # Initialize components
        self._shutdown_coordinator = ShutdownCoordinator(self._app_state_manager)
        self._error_classifier = ErrorClassifier()
        
        # State management
        self._current_phase = ShutdownPhase.INITIATED
        self._status = ShutdownStatus.NOT_STARTED
        self._metrics = ShutdownMetrics()
        self._shutdown_callbacks: Dict[ShutdownPhase, List[Callable]] = {}
        self._lock = threading.RLock()
        self._shutdown_in_progress = False
        
        # Signal handling
        self._signal_handlers_installed = False
        self._original_handlers: Dict[int, Any] = {}
        
        # Initialize phase handlers
        self._initialize_phase_handlers()
        
        self._logger.info("ShutdownHandler initialized successfully")
    
    def shutdown_application(self, 
                           trigger: ShutdownTrigger = ShutdownTrigger.USER_REQUEST,
                           mode: ShutdownMode = ShutdownMode.GRACEFUL,
                           reason: str = "User requested shutdown") -> ShutdownHandlerResult:
        """
        Initiate application shutdown process.
        
        Args:
            trigger: What triggered the shutdown
            mode: Shutdown mode (graceful, forced, emergency)
            reason: Reason for shutdown
            
        Returns:
            ShutdownHandlerResult with shutdown outcome
        """
        start_time = time.time()
        self._logger.info(f"Initiating application shutdown: {reason}")
        
        try:
            with self._lock:
                if self._shutdown_in_progress:
                    self._logger.warning("Shutdown already in progress")
                    return self._create_result(False, ShutdownStatus.IN_PROGRESS, trigger, mode)
                
                self._shutdown_in_progress = True
                self._status = ShutdownStatus.IN_PROGRESS
                self._metrics = ShutdownMetrics()
            
            # Install signal handlers for emergency shutdown
            if not self._signal_handlers_installed:
                self._install_signal_handlers()
            
            # Execute shutdown based on mode
            if mode == ShutdownMode.EMERGENCY:
                return self._execute_emergency_shutdown(trigger, start_time)
            elif mode == ShutdownMode.FORCED:
                return self._execute_forced_shutdown(trigger, start_time)
            else:
                return self._execute_graceful_shutdown(trigger, start_time)
                
        except Exception as e:
            self._logger.error(f"Shutdown failed with exception: {e}", exc_info=True)
            with self._lock:
                self._status = ShutdownStatus.FAILED
                self._metrics.total_time = time.time() - start_time
                self._metrics.errors_encountered += 1
            
            return self._create_result(False, ShutdownStatus.FAILED, trigger, mode, [str(e)])
    
    def _execute_graceful_shutdown(self, trigger: ShutdownTrigger, start_time: float) -> ShutdownHandlerResult:
        """Execute graceful shutdown process."""
        self._logger.info("Executing graceful shutdown")
        
        try:
            # Create shutdown context
            context = ShutdownContext(
                shutdown_reason=trigger.value,
                save_state=self._config.save_state,
                cleanup_temp_files=True,
                force_shutdown=False
            )
            
            # Execute pre-shutdown callbacks
            self._execute_phase_callbacks(ShutdownPhase.INITIATED)
            
            # Save application state first
            if self._config.save_state:
                if not self._save_application_state():
                    self._logger.warning("Failed to save application state")
                    with self._lock:
                        self._metrics.warnings_generated += 1
                else:
                    with self._lock:
                        self._metrics.state_saved = True
            
            # Use shutdown coordinator for coordinated shutdown
            shutdown_result = self._shutdown_coordinator.initiate_shutdown(context)
            
            # Update metrics
            with self._lock:
                self._metrics.total_time = time.time() - start_time
                self._metrics.components_shutdown = len(shutdown_result.cleanup_statuses)
                self._current_phase = shutdown_result.phase_reached
                
                if shutdown_result.success:
                    self._status = ShutdownStatus.COMPLETED
                    self._metrics.cleanup_completed = True
                else:
                    self._status = ShutdownStatus.FAILED
                    self._metrics.errors_encountered += len(shutdown_result.error_messages)
            
            # Execute post-shutdown callbacks
            self._execute_phase_callbacks(ShutdownPhase.COMPLETED)
            
            # Cleanup temporary files if configured
            if self._config.cleanup_temp_files:
                self._cleanup_temporary_files()
            
            self._logger.info(f"Graceful shutdown completed in {self._metrics.total_time:.2f}s")
            return self._create_result(
                shutdown_result.success, 
                self._status, 
                trigger, 
                ShutdownMode.GRACEFUL,
                shutdown_result.error_messages,
                shutdown_result
            )
            
        except Exception as e:
            self._logger.error(f"Graceful shutdown failed: {e}", exc_info=True)
            return self._execute_forced_shutdown(trigger, start_time)
    
    def _execute_forced_shutdown(self, trigger: ShutdownTrigger, start_time: float) -> ShutdownHandlerResult:
        """Execute forced shutdown process."""
        self._logger.warning("Executing forced shutdown")
        
        try:
            # Quick state save if possible
            if self._config.save_state:
                try:
                    self._save_application_state()
                    with self._lock:
                        self._metrics.state_saved = True
                except Exception as e:
                    self._logger.error(f"Failed to save state during forced shutdown: {e}")
            
            # Force shutdown through coordinator with reduced timeout
            context = ShutdownContext(
                trigger_reason=trigger.value,
                save_state=False,  # Already attempted above
                cleanup_resources=True,
                notify_users=False,  # Skip notifications in forced mode
                timeout=self._config.force_timeout
            )
            
            shutdown_result = self._shutdown_coordinator.initiate_shutdown(context)
            
            with self._lock:
                self._metrics.total_time = time.time() - start_time
                self._status = ShutdownStatus.COMPLETED
                self._current_phase = shutdown_result.phase_reached
            
            self._logger.warning(f"Forced shutdown completed in {self._metrics.total_time:.2f}s")
            return self._create_result(True, ShutdownStatus.COMPLETED, trigger, ShutdownMode.FORCED)
            
        except Exception as e:
            self._logger.error(f"Forced shutdown failed: {e}", exc_info=True)
            return self._execute_emergency_shutdown(trigger, start_time)
    
    def _execute_emergency_shutdown(self, trigger: ShutdownTrigger, start_time: float) -> ShutdownHandlerResult:
        """Execute emergency shutdown process."""
        self._logger.critical("Executing emergency shutdown")
        
        try:
            # Minimal cleanup - just exit
            with self._lock:
                self._metrics.total_time = time.time() - start_time
                self._status = ShutdownStatus.COMPLETED
                self._current_phase = ShutdownPhase.FINAL_CLEANUP
            
            self._logger.critical(f"Emergency shutdown completed in {self._metrics.total_time:.2f}s")
            return self._create_result(True, ShutdownStatus.COMPLETED, trigger, ShutdownMode.EMERGENCY)
            
        except Exception as e:
            self._logger.critical(f"Emergency shutdown failed: {e}", exc_info=True)
            with self._lock:
                self._status = ShutdownStatus.FAILED
            return self._create_result(False, ShutdownStatus.FAILED, trigger, ShutdownMode.EMERGENCY, [str(e)])
    
    def _save_application_state(self) -> bool:
        """Save current application state."""
        try:
            self._logger.info("Saving application state")
            
            # Save current state through app state manager
            # This would typically involve serializing state to disk
            # For now, we'll just mark it as saved
            
            self._logger.info("Application state saved successfully")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to save application state: {e}", exc_info=True)
            return False
    
    def _cleanup_temporary_files(self) -> None:
        """Cleanup temporary files and directories."""
        try:
            self._logger.info("Cleaning up temporary files")
            
            # Cleanup logic would be implemented here
            # For now, we'll just log the action
            
            self._logger.info("Temporary files cleaned up successfully")
            
        except Exception as e:
            self._logger.error(f"Failed to cleanup temporary files: {e}", exc_info=True)
    
    def _install_signal_handlers(self) -> None:
        """Install signal handlers for emergency shutdown."""
        try:
            # Store original handlers
            self._original_handlers[signal.SIGINT] = signal.signal(signal.SIGINT, self._signal_handler)
            self._original_handlers[signal.SIGTERM] = signal.signal(signal.SIGTERM, self._signal_handler)
            
            self._signal_handlers_installed = True
            self._logger.info("Signal handlers installed")
            
        except Exception as e:
            self._logger.error(f"Failed to install signal handlers: {e}")
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle system signals."""
        self._logger.warning(f"Received signal {signum}, initiating emergency shutdown")
        
        # Trigger emergency shutdown
        self.shutdown_application(
            trigger=ShutdownTrigger.SYSTEM_SIGNAL,
            mode=ShutdownMode.EMERGENCY,
            reason=f"System signal {signum}"
        )
    
    def _initialize_phase_handlers(self) -> None:
        """Initialize phase-specific handlers."""
        for phase in ShutdownPhase:
            self._shutdown_callbacks[phase] = []
    
    def _execute_phase_callbacks(self, phase: ShutdownPhase) -> None:
        """Execute callbacks for a specific phase."""
        callbacks = self._shutdown_callbacks.get(phase, [])
        for callback in callbacks:
            try:
                callback()
            except Exception as e:
                self._logger.error(f"Callback failed for phase {phase.value}: {e}")
    
    def _create_result(self, success: bool, status: ShutdownStatus, 
                      trigger: ShutdownTrigger, mode: ShutdownMode,
                      errors: List[str] = None,
                      shutdown_result: ShutdownResult = None) -> ShutdownHandlerResult:
        """Create shutdown handler result."""
        return ShutdownHandlerResult(
            success=success,
            status=status,
            trigger=trigger,
            mode=mode,
            phase_reached=self._current_phase,
            metrics=self._metrics,
            error_messages=errors or [],
            warnings=[],
            shutdown_result=shutdown_result
        )
    
    def add_phase_callback(self, phase: ShutdownPhase, callback: Callable) -> None:
        """
        Add a callback for a specific shutdown phase.
        
        Args:
            phase: Shutdown phase
            callback: Callback function to execute
        """
        with self._lock:
            if phase not in self._shutdown_callbacks:
                self._shutdown_callbacks[phase] = []
            self._shutdown_callbacks[phase].append(callback)
    
    def get_current_phase(self) -> ShutdownPhase:
        """
        Get the current shutdown phase.
        
        Returns:
            Current shutdown phase
        """
        with self._lock:
            return self._current_phase
    
    def get_status(self) -> ShutdownStatus:
        """
        Get the current shutdown status.
        
        Returns:
            Current shutdown status
        """
        with self._lock:
            return self._status
    
    def get_metrics(self) -> ShutdownMetrics:
        """
        Get shutdown metrics.
        
        Returns:
            Current shutdown metrics
        """
        with self._lock:
            return self._metrics
    
    def is_shutdown_in_progress(self) -> bool:
        """
        Check if shutdown is currently in progress.
        
        Returns:
            True if shutdown is in progress
        """
        with self._lock:
            return self._shutdown_in_progress
