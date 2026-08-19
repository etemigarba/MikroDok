"""
MikroDok Error Handling Package
Provides comprehensive error management and recovery functionality.
"""

# Import all error handling components
from .error_classifier_lg.error_classifier_lg import (
    ErrorClassifier,
    ErrorSeverity,
    ErrorCategory,
    ErrorContext,
    RecoveryAction,
    UserNotification,
    ClassificationResult
)

from .recovery_orchestrator_lg.recovery_orchestrator_lg import (
    RecoveryOrchestrator,
    RecoveryStrategy,
    RecoveryResult,
    RecoveryWorkflow
)

from .crash_handler_lg.crash_handler_lg import (
    CrashHandler,
    CrashType,
    CrashContext,
    RecoveryPoint
)

from .validation_engine_lg.validation_engine_lg import (
    ValidationEngine,
    ValidationRule,
    ValidationResult,
    ValidationError,
    ValidationSeverity
)

from .error_coordinator_lg.error_coordinator_lg import (
    ErrorHandlingCoordinator,
    ErrorHandlingMode,
    ErrorHandlingConfig,
    ErrorHandlingStats,
    get_error_coordinator,
    handle_error,
    validate_input
)

__all__ = [
    # Error Classification
    'ErrorClassifier',
    'ErrorSeverity',
    'ErrorCategory',
    'ErrorContext',
    'RecoveryAction',
    'UserNotification',
    'ClassificationResult',
    
    # Recovery Orchestration
    'RecoveryOrchestrator',
    'RecoveryStrategy',
    'RecoveryResult',
    'RecoveryWorkflow',
    
    # Crash Handling
    'CrashHandler',
    'CrashType',
    'CrashContext',
    'RecoveryPoint',
    
    # Validation
    'ValidationEngine',
    'ValidationRule',
    'ValidationResult',
    'ValidationError',
    'ValidationSeverity',

    # Error Coordination
    'ErrorHandlingCoordinator',
    'ErrorHandlingMode',
    'ErrorHandlingConfig',
    'ErrorHandlingStats',
    'get_error_coordinator',
    'handle_error',
    'validate_input'
]
