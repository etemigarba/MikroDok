"""
Module: system_coordinator_lg
Description: Centralized system initialization coordinator that orchestrates all initialization modules
Phase: 1
Location: /src/modules/logic/system_initialization_lg/system_coordinator_lg/
"""

# Standard library imports
import sys
import time
import threading
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Third-party imports
# None required for this module

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.system_initialization_lg.startup_orchestrator_lg.startup_orchestrator_lg import (
    StartupOrchestrator, StartupResult, StartupContext, InitializationPhase
)
from src.modules.logic.system_initialization_lg.preflight_checker_lg.preflight_checker_lg import (
    PreflightChecker, ValidationReport, RequirementStatus
)
from src.modules.logic.system_initialization_lg.shutdown_coordinator_lg.shutdown_coordinator_lg import (
    ShutdownCoordinator, ShutdownResult, ShutdownContext, ShutdownPhase
)
from src.modules.logic.system_initialization_lg.dependency_resolver_lg.dependency_resolver_lg import (
    DependencyResolver, ResolutionResult, DependencyNode
)
from src.modules.logic.error_handling_lg.error_coordinator_lg.error_coordinator_lg import (
    get_error_coordinator, ErrorHandlingConfig, ErrorHandlingMode
)


class SystemInitializationMode(Enum):
    """System initialization operation modes."""
    MINIMAL = "MINIMAL"          # Minimal initialization for basic functionality
    STANDARD = "STANDARD"        # Standard initialization with all checks
    COMPREHENSIVE = "COMPREHENSIVE"  # Comprehensive initialization with full validation
    DEVELOPMENT = "DEVELOPMENT"  # Development mode with detailed logging


@dataclass
class SystemInitializationConfig:
    """Configuration for system initialization coordinator."""
    mode: SystemInitializationMode = SystemInitializationMode.STANDARD
    enable_preflight_checks: bool = True
    enable_dependency_resolution: bool = True
    enable_startup_orchestration: bool = True
    enable_shutdown_coordination: bool = True
    enable_error_handling: bool = True
    initialization_timeout: float = 300.0  # 5 minutes
    validation_timeout: float = 60.0       # 1 minute
    parallel_initialization: bool = True
    strict_validation: bool = True
    debug_mode: bool = False


@dataclass
class SystemInitializationStats:
    """Statistics for system initialization operations."""
    total_initializations: int = 0
    successful_initializations: int = 0
    failed_initializations: int = 0
    preflight_checks_performed: int = 0
    dependencies_resolved: int = 0
    shutdowns_coordinated: int = 0
    last_initialization_time: Optional[datetime] = None
    average_initialization_time: float = 0.0


@dataclass
class SystemInitializationResult:
    """Result of system initialization process."""
    success: bool
    initialization_time: float
    preflight_result: Optional[ValidationReport] = None
    dependency_result: Optional[ResolutionResult] = None
    startup_result: Optional[StartupResult] = None
    error_messages: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    context: Optional[Dict[str, Any]] = None


class SystemInitializationCoordinator:
    """
    Centralized system initialization coordinator that orchestrates all initialization modules.
    
    This coordinator provides a unified interface for system initialization, managing the
    interaction between preflight checking, dependency resolution, startup orchestration,
    and shutdown coordination.
    """
    
    def __init__(self, config: Optional[SystemInitializationConfig] = None,
                 app_state_manager: Optional[AppStateManager] = None):
        """
        Initialize the system initialization coordinator.
        
        Args:
            config: System initialization configuration
            app_state_manager: Application state manager
        """
        self._config = config or SystemInitializationConfig()
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("system_coordinator")
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Statistics and monitoring
        self._stats = SystemInitializationStats()
        self._initialization_history: List[Dict[str, Any]] = []
        self._max_history_entries = 100
        
        # System initialization modules (initialized in order)
        self._preflight_checker: Optional[PreflightChecker] = None
        self._dependency_resolver: Optional[DependencyResolver] = None
        self._startup_orchestrator: Optional[StartupOrchestrator] = None
        self._shutdown_coordinator: Optional[ShutdownCoordinator] = None
        
        # Error handling integration
        self._error_coordinator = None
        if self._config.enable_error_handling:
            error_config = ErrorHandlingConfig(
                mode=ErrorHandlingMode.PRODUCTION if self._config.mode == SystemInitializationMode.STANDARD 
                     else ErrorHandlingMode.DEVELOPMENT
            )
            self._error_coordinator = get_error_coordinator(error_config)
        
        # Initialization callbacks
        self._initialization_callbacks: List[Callable[[SystemInitializationResult], None]] = []
        self._shutdown_callbacks: List[Callable[[ShutdownResult], None]] = []
        
        # Initialization state
        self._initialized = False
        self._initialization_time: Optional[datetime] = None
        
        self._logger.info("SystemInitializationCoordinator created with mode: %s", self._config.mode.value)
    
    def initialize_system(self, context: Optional[Dict[str, Any]] = None) -> SystemInitializationResult:
        """
        Initialize the complete system through coordinated initialization process.
        
        Args:
            context: Additional context information
            
        Returns:
            SystemInitializationResult with initialization outcome
        """
        if self._initialized:
            self._logger.warning("System already initialized")
            return SystemInitializationResult(
                success=True,
                initialization_time=0.0,
                warnings=["System already initialized"]
            )
        
        start_time = time.time()
        context = context or {}
        
        try:
            with self._lock:
                self._stats.total_initializations += 1
            
            # Create initialization context
            init_context = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'mode': self._config.mode.value,
                'config': self._config.__dict__,
                **context
            }
            
            self._logger.info("Starting system initialization", extra=init_context)
            
            # Initialize system modules in order
            result = SystemInitializationResult(
                success=True,
                initialization_time=0.0,
                context=init_context
            )
            
            # Step 1: Initialize core modules
            if not self._initialize_core_modules():
                result.success = False
                result.error_messages.append("Failed to initialize core modules")
                return result
            
            # Step 2: Perform preflight checks
            if self._config.enable_preflight_checks:
                preflight_result = self._perform_preflight_checks()
                result.preflight_result = preflight_result
                
                if not preflight_result.can_proceed:
                    result.success = False
                    result.error_messages.extend(preflight_result.errors)
                    return result
                
                result.warnings.extend(preflight_result.warnings)
            
            # Step 3: Resolve dependencies
            if self._config.enable_dependency_resolution:
                dependency_result = self._resolve_dependencies()
                result.dependency_result = dependency_result
                
                if not dependency_result.success:
                    result.success = False
                    result.error_messages.extend(dependency_result.error_messages)
                    return result
            
            # Step 4: Orchestrate startup
            if self._config.enable_startup_orchestration:
                startup_context = StartupContext(
                    debug_mode=self._config.debug_mode,
                    parallel_initialization=self._config.parallel_initialization
                )
                startup_result = self._startup_orchestrator.initialize_application(startup_context)
                result.startup_result = startup_result
                
                if not startup_result.success:
                    result.success = False
                    result.error_messages.extend(startup_result.error_messages)
                    return result
                
                result.warnings.extend(startup_result.warnings)
            
            # Mark as initialized
            initialization_time = time.time() - start_time
            result.initialization_time = initialization_time
            
            with self._lock:
                self._initialized = True
                self._initialization_time = datetime.now(timezone.utc)
                self._stats.successful_initializations += 1
                
                # Update average initialization time
                total_time = (self._stats.average_initialization_time * 
                             (self._stats.successful_initializations - 1) + initialization_time)
                self._stats.average_initialization_time = total_time / self._stats.successful_initializations
            
            # Add to history
            self._add_to_history(result)
            
            # Notify callbacks
            for callback in self._initialization_callbacks:
                try:
                    callback(result)
                except Exception as e:
                    self._logger.error("Initialization callback failed: %s", e)
            
            self._logger.info("System initialization completed successfully in %.3fs", initialization_time)
            return result
            
        except Exception as e:
            initialization_time = time.time() - start_time
            
            with self._lock:
                self._stats.failed_initializations += 1
            
            error_context = {
                'error_type': type(e).__name__,
                'error_message': str(e),
                'initialization_time': initialization_time
            }
            
            if self._error_coordinator:
                self._error_coordinator.handle_error(e, error_context)
            
            self._logger.error("System initialization failed: %s", e, extra=error_context)
            
            return SystemInitializationResult(
                success=False,
                initialization_time=initialization_time,
                error_messages=[f"System initialization failed: {e}"],
                context=init_context
            )
    
    def shutdown_system(self, context: Optional[Dict[str, Any]] = None) -> ShutdownResult:
        """
        Shutdown the system through coordinated shutdown process.
        
        Args:
            context: Additional context information
            
        Returns:
            ShutdownResult with shutdown outcome
        """
        if not self._initialized:
            self._logger.warning("System not initialized, cannot shutdown")
            return ShutdownResult(
                success=False,
                phase_reached=ShutdownPhase.INITIATED,
                total_time=0.0,
                error_messages=["System not initialized"]
            )
        
        try:
            if self._config.enable_shutdown_coordination and self._shutdown_coordinator:
                shutdown_context = ShutdownContext(
                    shutdown_reason="system_coordinator_request",
                    save_state=True,
                    cleanup_temp_files=True,
                    **(context or {})
                )
                
                result = self._shutdown_coordinator.initiate_shutdown(shutdown_context)
                
                with self._lock:
                    self._stats.shutdowns_coordinated += 1
                
                # Notify callbacks
                for callback in self._shutdown_callbacks:
                    try:
                        callback(result)
                    except Exception as e:
                        self._logger.error("Shutdown callback failed: %s", e)
                
                return result
            else:
                self._logger.info("Shutdown coordination disabled")
                return ShutdownResult(
                    success=True,
                    phase_reached=ShutdownPhase.COMPLETED,
                    total_time=0.0,
                    warnings=["Shutdown coordination disabled"]
                )
                
        except Exception as e:
            if self._error_coordinator:
                self._error_coordinator.handle_error(e, {
                    'component': 'system_coordinator',
                    'operation': 'shutdown'
                })
            
            self._logger.error("System shutdown failed: %s", e)
            return ShutdownResult(
                success=False,
                phase_reached=ShutdownPhase.INITIATED,
                total_time=0.0,
                error_messages=[f"System shutdown failed: {e}"]
            )

    def get_system_stats(self) -> SystemInitializationStats:
        """Get system initialization statistics."""
        with self._lock:
            return self._stats

    def is_system_initialized(self) -> bool:
        """Check if system is initialized."""
        with self._lock:
            return self._initialized

    def add_initialization_callback(self, callback: Callable[[SystemInitializationResult], None]) -> None:
        """Add initialization callback."""
        self._initialization_callbacks.append(callback)

    def add_shutdown_callback(self, callback: Callable[[ShutdownResult], None]) -> None:
        """Add shutdown callback."""
        self._shutdown_callbacks.append(callback)

    def _initialize_core_modules(self) -> bool:
        """Initialize core system modules."""
        try:
            # Initialize modules in dependency order
            if self._config.enable_dependency_resolution:
                self._dependency_resolver = DependencyResolver(self._app_state_manager)
                self._logger.debug("DependencyResolver initialized")

            if self._config.enable_preflight_checks:
                self._preflight_checker = PreflightChecker(self._app_state_manager)
                self._logger.debug("PreflightChecker initialized")

            if self._config.enable_startup_orchestration:
                self._startup_orchestrator = StartupOrchestrator(self._app_state_manager)
                self._logger.debug("StartupOrchestrator initialized")

            if self._config.enable_shutdown_coordination:
                self._shutdown_coordinator = ShutdownCoordinator(self._app_state_manager)
                self._logger.debug("ShutdownCoordinator initialized")

            return True

        except Exception as e:
            self._logger.error("Failed to initialize core modules: %s", e)
            return False

    def _perform_preflight_checks(self) -> ValidationReport:
        """Perform system preflight checks."""
        if not self._preflight_checker:
            return ValidationReport(
                overall_status=RequirementStatus.SKIPPED,
                can_proceed=True,
                warnings=["Preflight checker not available"]
            )

        try:
            with self._lock:
                self._stats.preflight_checks_performed += 1

            self._logger.info("Performing preflight checks")
            result = self._preflight_checker.validate_system_requirements()

            self._logger.info("Preflight checks completed: %s", result.overall_status.value)
            return result

        except Exception as e:
            self._logger.error("Preflight checks failed: %s", e)
            return ValidationReport(
                overall_status=RequirementStatus.FAILED,
                can_proceed=False,
                errors=[f"Preflight check error: {e}"]
            )

    def _resolve_dependencies(self) -> ResolutionResult:
        """Resolve system dependencies."""
        if not self._dependency_resolver:
            return ResolutionResult(
                success=True,
                resolved_order=[],
                warnings=["Dependency resolver not available"]
            )

        try:
            with self._lock:
                self._stats.dependencies_resolved += 1

            self._logger.info("Resolving dependencies")
            result = self._dependency_resolver.resolve_dependencies()

            self._logger.info("Dependency resolution completed: %s",
                            "success" if result.success else "failed")
            return result

        except Exception as e:
            self._logger.error("Dependency resolution failed: %s", e)
            return ResolutionResult(
                success=False,
                resolved_order=[],
                error_messages=[f"Dependency resolution error: {e}"]
            )

    def _add_to_history(self, result: SystemInitializationResult) -> None:
        """Add initialization result to history."""
        with self._lock:
            history_entry = {
                'timestamp': result.context.get('timestamp') if result.context else datetime.now(timezone.utc).isoformat(),
                'success': result.success,
                'initialization_time': result.initialization_time,
                'mode': self._config.mode.value,
                'error_count': len(result.error_messages),
                'warning_count': len(result.warnings)
            }

            self._initialization_history.append(history_entry)
            if len(self._initialization_history) > self._max_history_entries:
                self._initialization_history.pop(0)


# Global system initialization coordinator instance
_system_coordinator: Optional[SystemInitializationCoordinator] = None
_coordinator_lock = threading.Lock()


def get_system_coordinator(config: Optional[SystemInitializationConfig] = None,
                          app_state_manager: Optional[AppStateManager] = None) -> SystemInitializationCoordinator:
    """
    Get the global system initialization coordinator instance.

    Args:
        config: Optional configuration for first-time initialization
        app_state_manager: Optional application state manager

    Returns:
        SystemInitializationCoordinator instance
    """
    global _system_coordinator

    if _system_coordinator is None:
        with _coordinator_lock:
            if _system_coordinator is None:
                _system_coordinator = SystemInitializationCoordinator(config, app_state_manager)

    return _system_coordinator


def initialize_system(context: Optional[Dict[str, Any]] = None) -> SystemInitializationResult:
    """
    Convenience function to initialize system through the global coordinator.

    Args:
        context: Additional context information

    Returns:
        SystemInitializationResult with initialization outcome
    """
    coordinator = get_system_coordinator()
    return coordinator.initialize_system(context)


def shutdown_system(context: Optional[Dict[str, Any]] = None) -> ShutdownResult:
    """
    Convenience function to shutdown system through the global coordinator.

    Args:
        context: Additional context information

    Returns:
        ShutdownResult with shutdown outcome
    """
    coordinator = get_system_coordinator()
    return coordinator.shutdown_system(context)
