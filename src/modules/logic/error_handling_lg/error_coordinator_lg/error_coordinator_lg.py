"""
Module: error_coordinator_lg
Description: Centralized error handling coordinator that orchestrates all error handling modules
Phase: 1
Location: /src/modules/logic/error_handling_lg/error_coordinator_lg/
"""

# Standard library imports
import sys
import threading
import time
from typing import Dict, Any, Optional, List, Callable, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import json

# Third-party imports
# None required for this module

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.error_handling_lg.error_classifier_lg.error_classifier_lg import (
    ErrorClassifier, ErrorSeverity, ErrorCategory, ClassificationResult
)
from src.modules.logic.error_handling_lg.recovery_orchestrator_lg.recovery_orchestrator_lg import (
    RecoveryOrchestrator, RecoveryStrategy, RecoveryResult
)
from src.modules.logic.error_handling_lg.crash_handler_lg.crash_handler_lg import (
    CrashHandler, CrashType, CrashContext
)
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
    ValidationEngine, ValidationResult, ValidationSeverity
)


class ErrorHandlingMode(Enum):
    """Error handling operation modes."""
    STRICT = "STRICT"          # Strict error handling with immediate stops
    TOLERANT = "TOLERANT"      # Tolerant mode with recovery attempts
    DEVELOPMENT = "DEVELOPMENT" # Development mode with detailed logging
    PRODUCTION = "PRODUCTION"   # Production mode with user-friendly handling


@dataclass
class ErrorHandlingConfig:
    """Configuration for error handling coordinator."""
    mode: ErrorHandlingMode = ErrorHandlingMode.PRODUCTION
    enable_crash_handling: bool = True
    enable_auto_recovery: bool = True
    enable_validation: bool = True
    max_recovery_attempts: int = 3
    recovery_timeout: int = 30
    log_all_errors: bool = True
    user_notification_enabled: bool = True
    emergency_shutdown_enabled: bool = True


@dataclass
class ErrorHandlingStats:
    """Statistics for error handling operations."""
    total_errors_handled: int = 0
    successful_recoveries: int = 0
    failed_recoveries: int = 0
    crashes_prevented: int = 0
    validation_failures: int = 0
    last_error_time: Optional[datetime] = None
    uptime_since_last_crash: Optional[float] = None


class ErrorHandlingCoordinator:
    """
    Centralized error handling coordinator that orchestrates all error handling modules.
    
    This coordinator provides a unified interface for error handling across the application,
    managing the interaction between error classification, recovery orchestration, crash
    handling, and validation engines.
    """
    
    def __init__(self, config: Optional[ErrorHandlingConfig] = None):
        """
        Initialize the error handling coordinator.
        
        Args:
            config: Error handling configuration
        """
        self._config = config or ErrorHandlingConfig()
        self._log_manager = get_log_manager()
        self._logger = self._log_manager.get_logger("error_coordinator")
        self._app_state = AppStateManager()
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Statistics and monitoring
        self._stats = ErrorHandlingStats()
        self._error_history: List[Dict[str, Any]] = []
        self._max_history_entries = 1000
        
        # Error handling modules (initialized in order)
        self._validation_engine: Optional[ValidationEngine] = None
        self._error_classifier: Optional[ErrorClassifier] = None
        self._crash_handler: Optional[CrashHandler] = None
        self._recovery_orchestrator: Optional[RecoveryOrchestrator] = None
        
        # Error handling callbacks
        self._error_callbacks: List[Callable[[Exception, Dict[str, Any]], None]] = []
        self._recovery_callbacks: List[Callable[[RecoveryResult], None]] = []
        
        # Initialization state
        self._initialized = False
        self._initialization_time: Optional[datetime] = None
        
        self._logger.info("ErrorHandlingCoordinator created with mode: %s", self._config.mode.value)
    
    def initialize(self) -> bool:
        """
        Initialize all error handling modules in proper order.
        
        Returns:
            bool: True if initialization successful
        """
        if self._initialized:
            self._logger.warning("ErrorHandlingCoordinator already initialized")
            return True
        
        try:
            with self._lock:
                self._logger.info("Initializing error handling infrastructure...")
                start_time = time.time()
                
                # Initialize modules in dependency order
                if self._config.enable_validation:
                    self._validation_engine = ValidationEngine()
                    self._logger.debug("ValidationEngine initialized")
                
                self._error_classifier = ErrorClassifier()
                self._logger.debug("ErrorClassifier initialized")
                
                if self._config.enable_crash_handling:
                    self._crash_handler = CrashHandler()
                    self._logger.debug("CrashHandler initialized")
                
                if self._config.enable_auto_recovery:
                    self._recovery_orchestrator = RecoveryOrchestrator()
                    self._logger.debug("RecoveryOrchestrator initialized")
                
                # Set up global exception handler
                self._setup_global_exception_handler()
                
                # Mark as initialized
                self._initialized = True
                self._initialization_time = datetime.now(timezone.utc)
                
                init_time = time.time() - start_time
                self._logger.info("Error handling infrastructure initialized in %.3fs", init_time)
                
                return True
                
        except Exception as e:
            self._logger.error("Failed to initialize error handling infrastructure: %s", e)
            return False
    
    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Handle an error through the complete error handling pipeline.
        
        Args:
            error: The exception that occurred
            context: Additional context information
            
        Returns:
            bool: True if error was handled successfully
        """
        if not self._initialized:
            self._logger.error("Error handling coordinator not initialized")
            return False
        
        try:
            with self._lock:
                self._stats.total_errors_handled += 1
                self._stats.last_error_time = datetime.now(timezone.utc)
            
            # Create error context
            error_context = context or {}
            error_context.update({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error_type': type(error).__name__,
                'error_message': str(error),
                'handling_mode': self._config.mode.value
            })
            
            # Log error
            if self._config.log_all_errors:
                self._logger.error("Handling error: %s", error, extra=error_context)
            
            # Classify error
            classification = None
            if self._error_classifier:
                classification = self._error_classifier.classify_error(error, error_context)
                self._logger.debug("Error classified: %s -> %s", 
                                 type(error).__name__, classification.severity_level.value)
            
            # Handle critical errors immediately
            if classification and classification.severity_level == ErrorSeverity.CRITICAL:
                return self._handle_critical_error(error, classification, error_context)
            
            # Attempt recovery for recoverable errors
            if (classification and 
                classification.severity_level == ErrorSeverity.RECOVERABLE and 
                self._recovery_orchestrator):
                return self._attempt_recovery(error, classification, error_context)
            
            # Handle non-critical errors
            return self._handle_non_critical_error(error, classification, error_context)
            
        except Exception as handling_error:
            self._logger.critical("Error in error handling pipeline: %s", handling_error)
            return False
    
    def validate_input(self, data: Any, validation_rules: Optional[List] = None) -> ValidationResult:
        """
        Validate input data using the validation engine.
        
        Args:
            data: Data to validate
            validation_rules: Optional validation rules
            
        Returns:
            ValidationResult with validation outcome
        """
        if not self._validation_engine:
            self._logger.warning("ValidationEngine not available")
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                validation_time=0.0
            )
        
        try:
            result = self._validation_engine.validate(data, validation_rules)
            
            if not result.is_valid:
                with self._lock:
                    self._stats.validation_failures += 1
            
            return result
            
        except Exception as e:
            self._logger.error("Validation error: %s", e)
            return ValidationResult(
                is_valid=False,
                errors=[f"Validation engine error: {e}"],
                warnings=[],
                validation_time=0.0
            )
    
    def create_recovery_point(self, name: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Create a recovery point for crash recovery.
        
        Args:
            name: Recovery point name
            context: Additional context
            
        Returns:
            bool: True if recovery point created successfully
        """
        if not self._crash_handler:
            self._logger.warning("CrashHandler not available")
            return False
        
        try:
            return self._crash_handler.create_recovery_point(name, context)
        except Exception as e:
            self._logger.error("Failed to create recovery point: %s", e)
            return False
    
    def get_error_stats(self) -> ErrorHandlingStats:
        """Get error handling statistics."""
        with self._lock:
            # Calculate uptime since last crash
            if self._initialization_time:
                self._stats.uptime_since_last_crash = (
                    datetime.now(timezone.utc) - self._initialization_time
                ).total_seconds()
            
            return self._stats
    
    def add_error_callback(self, callback: Callable[[Exception, Dict[str, Any]], None]) -> None:
        """Add error handling callback."""
        self._error_callbacks.append(callback)
    
    def add_recovery_callback(self, callback: Callable[[RecoveryResult], None]) -> None:
        """Add recovery callback."""
        self._recovery_callbacks.append(callback)
    
    def shutdown(self) -> None:
        """Shutdown error handling coordinator."""
        self._logger.info("Shutting down error handling coordinator...")
        
        try:
            # Create final recovery point
            if self._crash_handler:
                self._crash_handler.create_recovery_point("shutdown_point")
            
            # Log final statistics
            stats = self.get_error_stats()
            self._logger.info("Error handling statistics: %s", {
                'total_errors': stats.total_errors_handled,
                'successful_recoveries': stats.successful_recoveries,
                'failed_recoveries': stats.failed_recoveries,
                'crashes_prevented': stats.crashes_prevented,
                'validation_failures': stats.validation_failures
            })
            
            self._initialized = False
            self._logger.info("Error handling coordinator shutdown complete")
            
        except Exception as e:
            self._logger.error("Error during shutdown: %s", e)

    def _setup_global_exception_handler(self) -> None:
        """Set up global exception handler."""
        def global_exception_handler(exc_type, exc_value, exc_traceback):
            """Global exception handler."""
            if issubclass(exc_type, KeyboardInterrupt):
                # Allow keyboard interrupt to pass through
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return

            # Handle through error coordinator
            self.handle_error(exc_value, {
                'exception_type': exc_type.__name__,
                'traceback': exc_traceback,
                'source': 'global_handler'
            })

        # Set global exception handler
        sys.excepthook = global_exception_handler

    def _handle_critical_error(self, error: Exception, classification: ClassificationResult,
                             context: Dict[str, Any]) -> bool:
        """Handle critical errors."""
        self._logger.critical("Critical error detected: %s", error)

        try:
            # Create emergency recovery point
            if self._crash_handler:
                self._crash_handler.create_recovery_point("critical_error_point", context)

            # Notify callbacks
            for callback in self._error_callbacks:
                try:
                    callback(error, context)
                except Exception as cb_error:
                    self._logger.error("Error callback failed: %s", cb_error)

            # Emergency shutdown if configured
            if self._config.emergency_shutdown_enabled:
                self._logger.critical("Initiating emergency shutdown")
                return False

            return True

        except Exception as e:
            self._logger.critical("Failed to handle critical error: %s", e)
            return False

    def _attempt_recovery(self, error: Exception, classification: ClassificationResult,
                         context: Dict[str, Any]) -> bool:
        """Attempt error recovery."""
        if not self._recovery_orchestrator:
            return False

        try:
            self._logger.info("Attempting recovery for error: %s", type(error).__name__)

            # Attempt recovery
            recovery_result = self._recovery_orchestrator.execute_recovery(classification, context)

            # Update statistics
            with self._lock:
                if recovery_result == RecoveryResult.SUCCESS:
                    self._stats.successful_recoveries += 1
                else:
                    self._stats.failed_recoveries += 1

            # Notify recovery callbacks
            for callback in self._recovery_callbacks:
                try:
                    callback(recovery_result)
                except Exception as cb_error:
                    self._logger.error("Recovery callback failed: %s", cb_error)

            return recovery_result == RecoveryResult.SUCCESS

        except Exception as e:
            self._logger.error("Recovery attempt failed: %s", e)
            with self._lock:
                self._stats.failed_recoveries += 1
            return False

    def _handle_non_critical_error(self, error: Exception, classification: Optional[ClassificationResult],
                                  context: Dict[str, Any]) -> bool:
        """Handle non-critical errors."""
        try:
            # Log error details
            self._logger.warning("Non-critical error: %s", error)

            # Add to error history
            with self._lock:
                error_entry = {
                    'timestamp': context.get('timestamp'),
                    'error_type': context.get('error_type'),
                    'error_message': context.get('error_message'),
                    'severity': classification.severity_level.value if classification else 'UNKNOWN',
                    'category': classification.error_category.value if classification else 'UNKNOWN'
                }

                self._error_history.append(error_entry)
                if len(self._error_history) > self._max_history_entries:
                    self._error_history.pop(0)

            # Notify callbacks
            for callback in self._error_callbacks:
                try:
                    callback(error, context)
                except Exception as cb_error:
                    self._logger.error("Error callback failed: %s", cb_error)

            return True

        except Exception as e:
            self._logger.error("Failed to handle non-critical error: %s", e)
            return False


# Global error handling coordinator instance
_error_coordinator: Optional[ErrorHandlingCoordinator] = None
_coordinator_lock = threading.Lock()


def get_error_coordinator(config: Optional[ErrorHandlingConfig] = None) -> ErrorHandlingCoordinator:
    """
    Get the global error handling coordinator instance.

    Args:
        config: Optional configuration for first-time initialization

    Returns:
        ErrorHandlingCoordinator instance
    """
    global _error_coordinator

    if _error_coordinator is None:
        with _coordinator_lock:
            if _error_coordinator is None:
                _error_coordinator = ErrorHandlingCoordinator(config)
                _error_coordinator.initialize()

    return _error_coordinator


def handle_error(error: Exception, context: Optional[Dict[str, Any]] = None) -> bool:
    """
    Convenience function to handle errors through the global coordinator.

    Args:
        error: The exception that occurred
        context: Additional context information

    Returns:
        bool: True if error was handled successfully
    """
    coordinator = get_error_coordinator()
    return coordinator.handle_error(error, context)


def validate_input(data: Any, validation_rules: Optional[List] = None) -> ValidationResult:
    """
    Convenience function to validate input through the global coordinator.

    Args:
        data: Data to validate
        validation_rules: Optional validation rules

    Returns:
        ValidationResult with validation outcome
    """
    coordinator = get_error_coordinator()
    return coordinator.validate_input(data, validation_rules)
