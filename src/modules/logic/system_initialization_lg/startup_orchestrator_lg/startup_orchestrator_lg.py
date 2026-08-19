"""
Module: startup_orchestrator_lg
Description: Manages application startup sequence and dependencies
Phase: 1
Location: /src/modules/logic/system_initialization_lg/startup_orchestrator_lg/
"""

# Standard library imports
import os
import sys
import time
import threading
from typing import Dict, List, Optional, Callable, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor, Future

# Third-party imports
# None required for this module

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager, log_performance
)
from src.modules.logic.error_handling_lg.error_classifier_lg.error_classifier_lg import (
    ErrorClassifier, ErrorSeverity, ErrorCategory, RecoveryAction
)
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
    ValidationEngine, ValidationResult
)
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager


class InitializationPhase(Enum):
    """Application initialization phases."""
    PREFLIGHT = "PREFLIGHT"
    CORE_SERVICES = "CORE_SERVICES"
    DATABASE = "DATABASE"
    RESOURCE_MONITORING = "RESOURCE_MONITORING"
    MEMORY_ALLOCATION = "MEMORY_ALLOCATION"
    UI_FRAMEWORK = "UI_FRAMEWORK"
    THEME_SYSTEM = "THEME_SYSTEM"
    APPLICATION_READY = "APPLICATION_READY"


class ComponentStatus(Enum):
    """Component initialization status."""
    PENDING = "PENDING"
    INITIALIZING = "INITIALIZING"
    INITIALIZED = "INITIALIZED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class StartupContext:
    """Context information for startup process."""
    command_line_args: Dict[str, Any] = field(default_factory=dict)
    system_environment: Dict[str, str] = field(default_factory=dict)
    startup_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    debug_mode: bool = False
    safe_mode: bool = False
    offline_mode: bool = True
    config_path: Optional[Path] = None


@dataclass
class StartupResult:
    """Result of startup process."""
    success: bool
    phase_reached: InitializationPhase
    total_time: float
    component_statuses: Dict[str, ComponentStatus] = field(default_factory=dict)
    error_messages: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    context: Optional[StartupContext] = None


class StartupOrchestrator:
    """
    Orchestrates complete application startup ensuring all components 
    initialize in correct order with proper error handling.
    
    Manages the startup sequence, coordinates component initialization,
    handles dependencies, and provides comprehensive error recovery.
    """
    
    def __init__(self, app_state_manager: Optional[AppStateManager] = None):
        """Initialize the startup orchestrator."""
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("startup_orchestrator")
        self._error_classifier = ErrorClassifier()
        self._validation_engine = ValidationEngine()
        
        # Startup state management
        self._current_phase = InitializationPhase.PREFLIGHT
        self._component_statuses: Dict[str, ComponentStatus] = {}
        self._initialization_callbacks: Dict[InitializationPhase, List[Callable]] = {}
        self._cleanup_callbacks: List[Callable] = []
        self._lock = threading.RLock()
        
        # Configuration
        self._max_initialization_time = 300  # seconds
        self._component_timeout = 30  # seconds per component
        self._retry_attempts = 3
        self._parallel_initialization = True
        
        # Initialize phase handlers
        self._initialize_phase_handlers()
        
        self._logger.info("StartupOrchestrator initialized successfully")
    
    def initialize_application(self, context: Optional[StartupContext] = None) -> StartupResult:
        """
        Initialize the complete application following the startup sequence.
        
        Args:
            context: Startup context with configuration and environment
            
        Returns:
            StartupResult with initialization outcome
        """
        start_time = time.time()
        context = context or StartupContext()
        
        self._logger.info("Starting application initialization")
        
        try:
            # Validate startup context
            validation_result = self._validate_startup_context(context)
            if not validation_result.is_valid:
                return self._create_failure_result(
                    InitializationPhase.PREFLIGHT,
                    start_time,
                    context,
                    validation_result.get_error_messages()
                )
            
            # Execute initialization phases
            for phase in InitializationPhase:
                self._logger.info(f"Starting initialization phase: {phase.value}")
                
                with self._lock:
                    self._current_phase = phase
                
                phase_result = self._execute_phase(phase, context)
                
                if not phase_result:
                    return self._create_failure_result(phase, start_time, context)
                
                self._logger.info(f"Completed initialization phase: {phase.value}")
            
            # Mark application as initialized
            self._app_state_manager.set_initialized(True)
            
            total_time = time.time() - start_time
            self._logger.info(f"Application initialization completed successfully in {total_time:.2f}s")
            
            return StartupResult(
                success=True,
                phase_reached=InitializationPhase.APPLICATION_READY,
                total_time=total_time,
                component_statuses=self._component_statuses.copy(),
                context=context
            )
            
        except Exception as e:
            self._logger.error(f"Application initialization failed: {str(e)}")
            return self._create_failure_result(
                self._current_phase,
                start_time,
                context,
                [str(e)]
            )
    
    def register_component_initializer(self, phase: InitializationPhase, 
                                     callback: Callable[[StartupContext], bool],
                                     component_name: str) -> None:
        """
        Register a component initializer for a specific phase.
        
        Args:
            phase: Initialization phase
            callback: Initialization callback function
            component_name: Name of the component
        """
        with self._lock:
            if phase not in self._initialization_callbacks:
                self._initialization_callbacks[phase] = []
            
            self._initialization_callbacks[phase].append((callback, component_name))
            self._component_statuses[component_name] = ComponentStatus.PENDING
        
        self._logger.info(f"Registered component initializer: {component_name} for phase {phase.value}")
    
    def register_cleanup_callback(self, callback: Callable[[], None]) -> None:
        """
        Register a cleanup callback for shutdown.
        
        Args:
            callback: Cleanup callback function
        """
        with self._lock:
            self._cleanup_callbacks.append(callback)
        
        self._logger.debug("Registered cleanup callback")

    def get_current_phase(self) -> InitializationPhase:
        """
        Get the current initialization phase.

        Returns:
            Current initialization phase
        """
        with self._lock:
            return self._current_phase

    def get_component_status(self, component_name: str) -> Optional[ComponentStatus]:
        """
        Get the status of a specific component.

        Args:
            component_name: Name of the component

        Returns:
            Component status or None if not found
        """
        with self._lock:
            return self._component_statuses.get(component_name)

    def get_all_component_statuses(self) -> Dict[str, ComponentStatus]:
        """
        Get all component statuses.

        Returns:
            Dictionary of component statuses
        """
        with self._lock:
            return self._component_statuses.copy()

    def cleanup_resources(self) -> None:
        """Execute all registered cleanup callbacks."""
        self._logger.info("Starting resource cleanup")

        with self._lock:
            cleanup_callbacks = self._cleanup_callbacks.copy()

        for callback in cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                self._logger.error(f"Error during cleanup: {str(e)}")

        self._logger.info("Resource cleanup completed")

    def _execute_phase(self, phase: InitializationPhase, context: StartupContext) -> bool:
        """
        Execute a specific initialization phase.

        Args:
            phase: Phase to execute
            context: Startup context

        Returns:
            True if phase completed successfully
        """
        try:
            # Get phase callbacks
            with self._lock:
                callbacks = self._initialization_callbacks.get(phase, [])

            if not callbacks:
                self._logger.debug(f"No callbacks registered for phase: {phase.value}")
                return True

            # Execute callbacks
            if self._parallel_initialization and len(callbacks) > 1:
                return self._execute_phase_parallel(callbacks, context)
            else:
                return self._execute_phase_sequential(callbacks, context)

        except Exception as e:
            self._logger.error(f"Error executing phase {phase.value}: {str(e)}")
            return False

    def _execute_phase_sequential(self, callbacks: List[Tuple[Callable, str]],
                                 context: StartupContext) -> bool:
        """
        Execute phase callbacks sequentially.

        Args:
            callbacks: List of (callback, component_name) tuples
            context: Startup context

        Returns:
            True if all callbacks succeeded
        """
        for callback, component_name in callbacks:
            if not self._execute_component_initializer(callback, component_name, context):
                return False

        return True

    def _execute_phase_parallel(self, callbacks: List[Tuple[Callable, str]],
                               context: StartupContext) -> bool:
        """
        Execute phase callbacks in parallel.

        Args:
            callbacks: List of (callback, component_name) tuples
            context: Startup context

        Returns:
            True if all callbacks succeeded
        """
        with ThreadPoolExecutor(max_workers=min(len(callbacks), 4)) as executor:
            futures = []

            for callback, component_name in callbacks:
                future = executor.submit(
                    self._execute_component_initializer,
                    callback,
                    component_name,
                    context
                )
                futures.append(future)

            # Wait for all futures to complete
            success = True
            for future in futures:
                try:
                    if not future.result(timeout=self._component_timeout):
                        success = False
                except Exception as e:
                    self._logger.error(f"Component initialization failed: {str(e)}")
                    success = False

            return success

    def _execute_component_initializer(self, callback: Callable, component_name: str,
                                     context: StartupContext) -> bool:
        """
        Execute a single component initializer.

        Args:
            callback: Component initialization callback
            component_name: Name of the component
            context: Startup context

        Returns:
            True if initialization succeeded
        """
        try:
            # Update component status
            with self._lock:
                self._component_statuses[component_name] = ComponentStatus.INITIALIZING

            self._logger.info(f"Initializing component: {component_name}")

            # Execute callback with timeout
            start_time = time.time()
            success = callback(context)
            execution_time = time.time() - start_time

            # Update status based on result
            with self._lock:
                if success:
                    self._component_statuses[component_name] = ComponentStatus.INITIALIZED
                    self._logger.info(f"Component initialized successfully: {component_name} ({execution_time:.2f}s)")
                else:
                    self._component_statuses[component_name] = ComponentStatus.FAILED
                    self._logger.error(f"Component initialization failed: {component_name}")

            return success

        except Exception as e:
            with self._lock:
                self._component_statuses[component_name] = ComponentStatus.FAILED

            self._logger.error(f"Exception during component initialization {component_name}: {str(e)}")
            return False

    def _validate_startup_context(self, context: StartupContext) -> ValidationResult:
        """
        Validate startup context.

        Args:
            context: Startup context to validate

        Returns:
            ValidationResult with validation outcome
        """
        # Create validation data
        validation_data = {
            "command_line_args": context.command_line_args,
            "system_environment": context.system_environment,
            "debug_mode": context.debug_mode,
            "safe_mode": context.safe_mode,
            "offline_mode": context.offline_mode
        }

        # Validate using validation engine
        return self._validation_engine.validate_data(validation_data, "startup_context")

    def _create_failure_result(self, phase: InitializationPhase, start_time: float,
                              context: StartupContext, error_messages: List[str] = None) -> StartupResult:
        """
        Create a failure result.

        Args:
            phase: Phase where failure occurred
            start_time: Startup start time
            context: Startup context
            error_messages: List of error messages

        Returns:
            StartupResult indicating failure
        """
        total_time = time.time() - start_time

        return StartupResult(
            success=False,
            phase_reached=phase,
            total_time=total_time,
            component_statuses=self._component_statuses.copy(),
            error_messages=error_messages or [],
            context=context
        )

    def _initialize_phase_handlers(self) -> None:
        """Initialize built-in phase handlers."""
        # Register validation schema for startup context
        from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
            RequiredRule, TypeRule
        )

        startup_context_rules = [
            TypeRule("command_line_args", dict, "Command line args must be a dictionary"),
            TypeRule("system_environment", dict, "System environment must be a dictionary"),
            TypeRule("debug_mode", bool, "Debug mode must be a boolean"),
            TypeRule("safe_mode", bool, "Safe mode must be a boolean"),
            TypeRule("offline_mode", bool, "Offline mode must be a boolean")
        ]

        self._validation_engine.register_schema("startup_context", startup_context_rules)

        self._logger.debug("Phase handlers initialized")

    def _get_system_environment(self) -> Dict[str, str]:
        """
        Get system environment variables.

        Returns:
            Dictionary of environment variables
        """
        return dict(os.environ)

    def _parse_command_line_args(self, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Parse command line arguments.

        Args:
            args: Command line arguments (defaults to sys.argv)

        Returns:
            Dictionary of parsed arguments
        """
        if args is None:
            args = sys.argv[1:]

        parsed_args = {}

        for arg in args:
            if arg.startswith('--'):
                if '=' in arg:
                    key, value = arg[2:].split('=', 1)
                    parsed_args[key] = value
                else:
                    parsed_args[arg[2:]] = True
            elif arg.startswith('-'):
                parsed_args[arg[1:]] = True

        return parsed_args
