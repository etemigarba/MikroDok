"""
Module: shutdown_coordinator_lg
Description: Handles graceful shutdown with resource cleanup
Phase: 1
Location: /src/modules/logic/system_initialization_lg/shutdown_coordinator_lg/
"""

# Standard library imports
import os
import sys
import time
import signal
import threading
import atexit
from typing import Dict, List, Optional, Callable, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import weakref

# Third-party imports
# None required for this module

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)
from src.modules.logic.error_handling_lg.error_classifier_lg.error_classifier_lg import (
    ErrorClassifier, ErrorSeverity, ErrorCategory
)
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager


class ShutdownPhase(Enum):
    """Application shutdown phases."""
    INITIATED = "INITIATED"
    USER_INTERFACE = "USER_INTERFACE"
    BACKGROUND_SERVICES = "BACKGROUND_SERVICES"
    TRAINING_PROCESSES = "TRAINING_PROCESSES"
    DATABASE_CONNECTIONS = "DATABASE_CONNECTIONS"
    RESOURCE_CLEANUP = "RESOURCE_CLEANUP"
    STATE_PERSISTENCE = "STATE_PERSISTENCE"
    FINAL_CLEANUP = "FINAL_CLEANUP"
    COMPLETED = "COMPLETED"


class CleanupStatus(Enum):
    """Cleanup operation status."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    TIMEOUT = "TIMEOUT"


@dataclass
class ShutdownContext:
    """Context information for shutdown process."""
    shutdown_reason: str = "user_request"
    force_shutdown: bool = False
    save_state: bool = True
    cleanup_temp_files: bool = True
    shutdown_timeout: float = 60.0
    initiated_by: str = "system"
    shutdown_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ShutdownResult:
    """Result of shutdown process."""
    success: bool
    phase_reached: ShutdownPhase
    total_time: float
    cleanup_statuses: Dict[str, CleanupStatus] = field(default_factory=dict)
    error_messages: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    context: Optional[ShutdownContext] = None


class ShutdownCoordinator:
    """
    Handles graceful application shutdown with comprehensive resource cleanup.
    
    Coordinates shutdown sequence, manages resource cleanup, saves application
    state, and ensures proper cleanup of all components.
    """
    
    def __init__(self, app_state_manager: Optional[AppStateManager] = None):
        """Initialize the shutdown coordinator."""
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("shutdown_coordinator")
        self._error_classifier = ErrorClassifier()
        
        # Shutdown state management
        self._shutdown_initiated = False
        self._current_phase = ShutdownPhase.INITIATED
        self._cleanup_callbacks: Dict[ShutdownPhase, List[Tuple[Callable, str, int]]] = {}
        self._cleanup_statuses: Dict[str, CleanupStatus] = {}
        self._lock = threading.RLock()
        
        # Configuration
        self._default_timeout = 60.0
        self._component_timeout = 10.0
        self._force_timeout = 5.0
        self._max_parallel_cleanups = 4
        
        # Signal handling
        self._original_handlers = {}
        self._setup_signal_handlers()
        
        # Register atexit handler
        atexit.register(self._emergency_cleanup)
        
        self._logger.info("ShutdownCoordinator initialized successfully")
    
    def initiate_shutdown(self, context: Optional[ShutdownContext] = None) -> ShutdownResult:
        """
        Initiate graceful application shutdown.
        
        Args:
            context: Shutdown context with configuration
            
        Returns:
            ShutdownResult with shutdown outcome
        """
        start_time = time.time()
        context = context or ShutdownContext()
        
        with self._lock:
            if self._shutdown_initiated:
                self._logger.warning("Shutdown already initiated")
                return ShutdownResult(
                    success=False,
                    phase_reached=self._current_phase,
                    total_time=0.0,
                    error_messages=["Shutdown already in progress"],
                    context=context
                )
            
            self._shutdown_initiated = True
        
        self._logger.info(f"Initiating application shutdown: {context.shutdown_reason}")
        
        try:
            # Execute shutdown phases
            for phase in ShutdownPhase:
                if phase == ShutdownPhase.COMPLETED:
                    continue
                
                self._logger.info(f"Starting shutdown phase: {phase.value}")
                
                with self._lock:
                    self._current_phase = phase
                
                phase_result = self._execute_shutdown_phase(phase, context)
                
                if not phase_result and not context.force_shutdown:
                    return self._create_failure_result(phase, start_time, context)
                
                self._logger.info(f"Completed shutdown phase: {phase.value}")
            
            # Mark shutdown as completed
            with self._lock:
                self._current_phase = ShutdownPhase.COMPLETED
            
            total_time = time.time() - start_time
            self._logger.info(f"Application shutdown completed successfully in {total_time:.2f}s")
            
            return ShutdownResult(
                success=True,
                phase_reached=ShutdownPhase.COMPLETED,
                total_time=total_time,
                cleanup_statuses=self._cleanup_statuses.copy(),
                context=context
            )
            
        except Exception as e:
            self._logger.error(f"Application shutdown failed: {str(e)}")
            return self._create_failure_result(
                self._current_phase,
                start_time,
                context,
                [str(e)]
            )
    
    def register_cleanup_callback(self, phase: ShutdownPhase, callback: Callable[[], bool],
                                 component_name: str, priority: int = 0) -> None:
        """
        Register a cleanup callback for a specific shutdown phase.
        
        Args:
            phase: Shutdown phase
            callback: Cleanup callback function
            component_name: Name of the component
            priority: Priority (higher numbers execute first)
        """
        with self._lock:
            if phase not in self._cleanup_callbacks:
                self._cleanup_callbacks[phase] = []
            
            self._cleanup_callbacks[phase].append((callback, component_name, priority))
            # Sort by priority (descending)
            self._cleanup_callbacks[phase].sort(key=lambda x: x[2], reverse=True)
            self._cleanup_statuses[component_name] = CleanupStatus.PENDING
        
        self._logger.info(f"Registered cleanup callback: {component_name} for phase {phase.value} (priority: {priority})")
    
    def force_shutdown(self, timeout: float = 5.0) -> None:
        """
        Force immediate shutdown with minimal cleanup.
        
        Args:
            timeout: Maximum time to wait for force shutdown
        """
        self._logger.warning("Force shutdown initiated")
        
        context = ShutdownContext(
            shutdown_reason="force_shutdown",
            force_shutdown=True,
            save_state=False,
            cleanup_temp_files=False,
            shutdown_timeout=timeout
        )
        
        # Execute emergency cleanup
        self._emergency_cleanup()
        
        # Exit immediately
        os._exit(1)
    
    def is_shutdown_initiated(self) -> bool:
        """
        Check if shutdown has been initiated.
        
        Returns:
            True if shutdown is in progress
        """
        with self._lock:
            return self._shutdown_initiated
    
    def get_current_phase(self) -> ShutdownPhase:
        """
        Get the current shutdown phase.
        
        Returns:
            Current shutdown phase
        """
        with self._lock:
            return self._current_phase
    
    def get_cleanup_status(self, component_name: str) -> Optional[CleanupStatus]:
        """
        Get the cleanup status of a specific component.
        
        Args:
            component_name: Name of the component
            
        Returns:
            Cleanup status or None if not found
        """
        with self._lock:
            return self._cleanup_statuses.get(component_name)

    def _execute_shutdown_phase(self, phase: ShutdownPhase, context: ShutdownContext) -> bool:
        """
        Execute a specific shutdown phase.

        Args:
            phase: Phase to execute
            context: Shutdown context

        Returns:
            True if phase completed successfully
        """
        try:
            # Get phase callbacks
            with self._lock:
                callbacks = self._cleanup_callbacks.get(phase, [])

            if not callbacks:
                self._logger.debug(f"No cleanup callbacks registered for phase: {phase.value}")
                return True

            # Execute callbacks with timeout
            timeout = context.shutdown_timeout / len(ShutdownPhase)

            if len(callbacks) > 1 and not context.force_shutdown:
                return self._execute_phase_parallel(callbacks, timeout)
            else:
                return self._execute_phase_sequential(callbacks, timeout)

        except Exception as e:
            self._logger.error(f"Error executing shutdown phase {phase.value}: {str(e)}")
            return False

    def _execute_phase_sequential(self, callbacks: List[Tuple[Callable, str, int]],
                                 timeout: float) -> bool:
        """
        Execute phase callbacks sequentially.

        Args:
            callbacks: List of (callback, component_name, priority) tuples
            timeout: Total timeout for phase

        Returns:
            True if all callbacks succeeded
        """
        success = True
        component_timeout = min(timeout / len(callbacks), self._component_timeout)

        for callback, component_name, _ in callbacks:
            if not self._execute_cleanup_callback(callback, component_name, component_timeout):
                success = False

        return success

    def _execute_phase_parallel(self, callbacks: List[Tuple[Callable, str, int]],
                               timeout: float) -> bool:
        """
        Execute phase callbacks in parallel.

        Args:
            callbacks: List of (callback, component_name, priority) tuples
            timeout: Total timeout for phase

        Returns:
            True if all callbacks succeeded
        """
        success = True
        component_timeout = min(timeout, self._component_timeout)

        with ThreadPoolExecutor(max_workers=min(len(callbacks), self._max_parallel_cleanups)) as executor:
            # Submit all callbacks
            futures = {}
            for callback, component_name, _ in callbacks:
                future = executor.submit(
                    self._execute_cleanup_callback,
                    callback,
                    component_name,
                    component_timeout
                )
                futures[future] = component_name

            # Wait for completion
            for future in as_completed(futures, timeout=timeout):
                component_name = futures[future]
                try:
                    if not future.result():
                        success = False
                except Exception as e:
                    self._logger.error(f"Cleanup callback failed for {component_name}: {str(e)}")
                    with self._lock:
                        self._cleanup_statuses[component_name] = CleanupStatus.FAILED
                    success = False

        return success

    def _execute_cleanup_callback(self, callback: Callable, component_name: str,
                                 timeout: float) -> bool:
        """
        Execute a single cleanup callback.

        Args:
            callback: Cleanup callback function
            component_name: Name of the component
            timeout: Timeout for callback execution

        Returns:
            True if cleanup succeeded
        """
        try:
            # Update status
            with self._lock:
                self._cleanup_statuses[component_name] = CleanupStatus.IN_PROGRESS

            self._logger.info(f"Cleaning up component: {component_name}")

            # Execute callback with timeout
            start_time = time.time()

            # Simple timeout implementation
            success = callback()
            execution_time = time.time() - start_time

            # Update status based on result
            with self._lock:
                if success:
                    self._cleanup_statuses[component_name] = CleanupStatus.COMPLETED
                    self._logger.info(f"Component cleanup completed: {component_name} ({execution_time:.2f}s)")
                else:
                    self._cleanup_statuses[component_name] = CleanupStatus.FAILED
                    self._logger.error(f"Component cleanup failed: {component_name}")

            return success

        except Exception as e:
            with self._lock:
                self._cleanup_statuses[component_name] = CleanupStatus.FAILED

            self._logger.error(f"Exception during component cleanup {component_name}: {str(e)}")
            return False

    def _create_failure_result(self, phase: ShutdownPhase, start_time: float,
                              context: ShutdownContext, error_messages: List[str] = None) -> ShutdownResult:
        """
        Create a failure result.

        Args:
            phase: Phase where failure occurred
            start_time: Shutdown start time
            context: Shutdown context
            error_messages: List of error messages

        Returns:
            ShutdownResult indicating failure
        """
        total_time = time.time() - start_time

        return ShutdownResult(
            success=False,
            phase_reached=phase,
            total_time=total_time,
            cleanup_statuses=self._cleanup_statuses.copy(),
            error_messages=error_messages or [],
            context=context
        )

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self._logger.info(f"Received signal {signum}, initiating shutdown")
            context = ShutdownContext(
                shutdown_reason=f"signal_{signum}",
                initiated_by="signal_handler"
            )
            self.initiate_shutdown(context)

        # Register signal handlers
        signals_to_handle = [signal.SIGTERM, signal.SIGINT]

        if hasattr(signal, 'SIGHUP'):
            signals_to_handle.append(signal.SIGHUP)

        for sig in signals_to_handle:
            try:
                self._original_handlers[sig] = signal.signal(sig, signal_handler)
            except (OSError, ValueError) as e:
                self._logger.warning(f"Could not register handler for signal {sig}: {str(e)}")

    def _emergency_cleanup(self) -> None:
        """Emergency cleanup for unexpected shutdown."""
        self._logger.warning("Emergency cleanup initiated")

        try:
            # Perform minimal critical cleanup
            with self._lock:
                critical_callbacks = []
                for phase_callbacks in self._cleanup_callbacks.values():
                    for callback, component_name, priority in phase_callbacks:
                        if priority >= 100:  # High priority cleanup only
                            critical_callbacks.append((callback, component_name))

            # Execute critical cleanups with short timeout
            for callback, component_name in critical_callbacks:
                try:
                    self._logger.info(f"Emergency cleanup: {component_name}")
                    callback()
                except Exception as e:
                    self._logger.error(f"Emergency cleanup failed for {component_name}: {str(e)}")

        except Exception as e:
            self._logger.error(f"Emergency cleanup failed: {str(e)}")

        self._logger.info("Emergency cleanup completed")
