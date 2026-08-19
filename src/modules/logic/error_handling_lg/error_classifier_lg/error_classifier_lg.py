"""
Module: error_classifier_lg
Description: Categorizes errors by severity and determines recovery strategies
Phase: 1
Location: /src/modules/logic/error_handling_lg/error_classifier_lg/
"""

# Standard library imports
import sys
import traceback
from typing import Dict, Any, Optional, List, Tuple, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
import hashlib
import json

# Third-party imports
# None required for this module

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager


class ErrorSeverity(Enum):
    """Error severity levels for classification."""
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"
    RECOVERABLE = "RECOVERABLE"


class ErrorCategory(Enum):
    """Error categories for classification."""
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
    TRAINING_INTERRUPTION = "TRAINING_INTERRUPTION"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    IO_ERROR = "IO_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    DATA_CORRUPTION = "DATA_CORRUPTION"
    SYSTEM_FAILURE = "SYSTEM_FAILURE"
    USER_ERROR = "USER_ERROR"
    UNKNOWN = "UNKNOWN"


class RecoveryAction(Enum):
    """Recovery actions for error handling."""
    RETRY = "RETRY"
    ROLLBACK = "ROLLBACK"
    RESTART = "RESTART"
    DEGRADE = "DEGRADE"
    ABORT = "ABORT"
    IGNORE = "IGNORE"
    USER_INTERVENTION = "USER_INTERVENTION"
    CHECKPOINT_RESTORE = "CHECKPOINT_RESTORE"


@dataclass
class ErrorContext:
    """Context information for error classification."""
    error_code: int
    error_type: str
    error_message: str
    operation_type: str
    timestamp: datetime
    affected_resources: List[str] = field(default_factory=list)
    system_state: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            'error_code': self.error_code,
            'error_type': self.error_type,
            'error_message': self.error_message,
            'operation_type': self.operation_type,
            'timestamp': self.timestamp.isoformat(),
            'affected_resources': self.affected_resources,
            'system_state': self.system_state,
            'stack_trace': self.stack_trace,
            'session_id': self.session_id,
            'user_id': self.user_id
        }


@dataclass
class UserNotification:
    """User notification configuration."""
    notification_type: str  # modal, toast, status_bar
    title: str
    message: str
    technical_details: Optional[str] = None
    suggested_actions: List[str] = field(default_factory=list)
    severity_color: str = "#000000"
    auto_dismiss: bool = False
    dismiss_timeout: int = 5000  # milliseconds


@dataclass
class ClassificationResult:
    """Result of error classification."""
    severity_level: ErrorSeverity
    error_category: ErrorCategory
    recovery_action: RecoveryAction
    user_notification: UserNotification
    confidence_score: float = 1.0
    classification_metadata: Dict[str, Any] = field(default_factory=dict)


class ErrorClassifier:
    """
    Categorizes errors by severity and determines recovery strategies.
    
    This class implements the error classification algorithm from the design
    documents, providing comprehensive error analysis and recovery recommendations.
    """
    
    def __init__(self):
        """Initialize the error classifier."""
        self._log_manager = get_log_manager()
        self._logger = self._log_manager.get_logger("error_classifier")
        self._app_state = AppStateManager()
        self._classification_cache: Dict[str, ClassificationResult] = {}
        self._lock = threading.RLock()
        
        # Initialize classification rules
        self._severity_rules = self._initialize_severity_rules()
        self._category_rules = self._initialize_category_rules()
        self._recovery_rules = self._initialize_recovery_rules()
        
        self._logger.info("ErrorClassifier initialized successfully")
    
    def classify_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> ClassificationResult:
        """
        Classify an error and determine recovery strategy.
        
        Args:
            error: The exception that occurred
            context: Additional context information
            
        Returns:
            ClassificationResult with severity, category, and recovery action
        """
        try:
            # Create error context
            error_context = self._create_error_context(error, context or {})
            
            # Check cache for similar errors
            cache_key = self._generate_cache_key(error_context)
            with self._lock:
                if cache_key in self._classification_cache:
                    cached_result = self._classification_cache[cache_key]
                    self._logger.debug(f"Using cached classification for error: {error_context.error_type}")
                    return cached_result
            
            # Perform classification
            severity = self._classify_severity(error_context)
            category = self._classify_category(error_context)
            recovery_action = self._determine_recovery_action(severity, category, error_context)
            user_notification = self._create_user_notification(severity, category, error_context)
            
            # Create result
            result = ClassificationResult(
                severity_level=severity,
                error_category=category,
                recovery_action=recovery_action,
                user_notification=user_notification,
                confidence_score=self._calculate_confidence(error_context, severity, category),
                classification_metadata={
                    'classification_time': datetime.now(timezone.utc).isoformat(),
                    'classifier_version': '1.0.0',
                    'context_hash': cache_key
                }
            )
            
            # Cache result
            with self._lock:
                self._classification_cache[cache_key] = result
                # Limit cache size
                if len(self._classification_cache) > 1000:
                    oldest_key = next(iter(self._classification_cache))
                    del self._classification_cache[oldest_key]
            
            # Log classification
            self._log_classification(error_context, result)
            
            return result
            
        except Exception as classification_error:
            self._logger.error(f"Error during classification: {classification_error}")
            # Return safe default classification
            return self._create_default_classification(error)
    
    def _create_error_context(self, error: Exception, context: Dict[str, Any]) -> ErrorContext:
        """Create error context from exception and additional context."""
        return ErrorContext(
            error_code=hash(str(error)) % 100000,
            error_type=type(error).__name__,
            error_message=str(error),
            operation_type=context.get('operation_type', 'unknown'),
            timestamp=datetime.now(timezone.utc),
            affected_resources=context.get('affected_resources', []),
            system_state=context.get('system_state', {}),
            stack_trace=traceback.format_exc(),
            session_id=context.get('session_id'),
            user_id=context.get('user_id')
        )
    
    def _generate_cache_key(self, context: ErrorContext) -> str:
        """Generate cache key for error context."""
        key_data = f"{context.error_type}:{context.operation_type}:{context.error_message[:100]}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _classify_severity(self, context: ErrorContext) -> ErrorSeverity:
        """Classify error severity based on context."""
        # Check for critical conditions
        if any(keyword in context.error_message.lower() for keyword in 
               ['memory', 'gpu', 'cuda', 'out of memory', 'allocation failed']):
            return ErrorSeverity.CRITICAL
        
        if any(keyword in context.error_type.lower() for keyword in 
               ['system', 'fatal', 'critical', 'crash']):
            return ErrorSeverity.CRITICAL
        
        # Check for recoverable conditions
        if any(keyword in context.error_message.lower() for keyword in 
               ['training', 'checkpoint', 'resume', 'interrupt']):
            return ErrorSeverity.RECOVERABLE
        
        # Check for warnings
        if any(keyword in context.error_message.lower() for keyword in 
               ['warning', 'deprecated', 'performance']):
            return ErrorSeverity.WARNING
        
        # Default to INFO for minor issues
        return ErrorSeverity.INFO
    
    def _classify_category(self, context: ErrorContext) -> ErrorCategory:
        """Classify error category based on context."""
        error_msg_lower = context.error_message.lower()
        error_type_lower = context.error_type.lower()
        
        # Resource exhaustion
        if any(keyword in error_msg_lower for keyword in 
               ['memory', 'gpu', 'vram', 'disk', 'storage', 'allocation']):
            return ErrorCategory.RESOURCE_EXHAUSTION
        
        # Training interruption
        if any(keyword in error_msg_lower for keyword in 
               ['training', 'epoch', 'batch', 'gradient', 'loss']):
            return ErrorCategory.TRAINING_INTERRUPTION
        
        # Validation failure
        if any(keyword in error_msg_lower for keyword in 
               ['validation', 'invalid', 'format', 'schema']):
            return ErrorCategory.VALIDATION_FAILURE
        
        # IO errors
        if any(keyword in error_type_lower for keyword in 
               ['io', 'file', 'permission', 'access']):
            return ErrorCategory.IO_ERROR
        
        # Configuration errors
        if any(keyword in error_msg_lower for keyword in 
               ['config', 'setting', 'parameter', 'option']):
            return ErrorCategory.CONFIGURATION_ERROR
        
        return ErrorCategory.UNKNOWN

    def _determine_recovery_action(self, severity: ErrorSeverity, category: ErrorCategory,
                                 context: ErrorContext) -> RecoveryAction:
        """Determine appropriate recovery action."""
        # Critical errors require immediate action
        if severity == ErrorSeverity.CRITICAL:
            if category == ErrorCategory.RESOURCE_EXHAUSTION:
                return RecoveryAction.CHECKPOINT_RESTORE
            elif category == ErrorCategory.SYSTEM_FAILURE:
                return RecoveryAction.RESTART
            else:
                return RecoveryAction.ABORT

        # Recoverable errors can be retried or rolled back
        if severity == ErrorSeverity.RECOVERABLE:
            if category == ErrorCategory.TRAINING_INTERRUPTION:
                return RecoveryAction.CHECKPOINT_RESTORE
            else:
                return RecoveryAction.RETRY

        # Warnings can be handled with degradation
        if severity == ErrorSeverity.WARNING:
            return RecoveryAction.DEGRADE

        # Info level errors can be ignored
        return RecoveryAction.IGNORE

    def _create_user_notification(self, severity: ErrorSeverity, category: ErrorCategory,
                                context: ErrorContext) -> UserNotification:
        """Create user notification based on classification."""
        if severity == ErrorSeverity.CRITICAL:
            return UserNotification(
                notification_type="modal",
                title="Critical Error",
                message=f"A critical error occurred: {context.error_message}",
                technical_details=context.stack_trace,
                suggested_actions=["Save work", "Restart application", "Check system resources"],
                severity_color="#DC2626",
                auto_dismiss=False
            )
        elif severity == ErrorSeverity.WARNING:
            return UserNotification(
                notification_type="toast",
                title="Warning",
                message=f"Warning: {context.error_message}",
                suggested_actions=["Review settings", "Continue with caution"],
                severity_color="#F59E0B",
                auto_dismiss=True,
                dismiss_timeout=8000
            )
        else:
            return UserNotification(
                notification_type="status_bar",
                title="Information",
                message=context.error_message,
                severity_color="#6B7280",
                auto_dismiss=True,
                dismiss_timeout=5000
            )

    def _calculate_confidence(self, context: ErrorContext, severity: ErrorSeverity,
                            category: ErrorCategory) -> float:
        """Calculate confidence score for classification."""
        confidence = 0.5  # Base confidence

        # Increase confidence for well-known error patterns
        if context.error_type in ['MemoryError', 'OutOfMemoryError', 'CudaOutOfMemoryError']:
            confidence += 0.4

        # Increase confidence if stack trace is available
        if context.stack_trace:
            confidence += 0.1

        # Ensure confidence is between 0 and 1
        return min(1.0, max(0.0, confidence))

    def _log_classification(self, context: ErrorContext, result: ClassificationResult) -> None:
        """Log the error classification result."""
        log_data = {
            'error_context': context.to_dict(),
            'classification_result': {
                'severity': result.severity_level.value,
                'category': result.error_category.value,
                'recovery_action': result.recovery_action.value,
                'confidence': result.confidence_score
            }
        }

        self._logger.info(f"Error classified: {context.error_type} -> {result.severity_level.value}")
        self._log_manager.log_error_with_context(
            Exception(context.error_message),
            log_data,
            "error_classifier"
        )

    def _create_default_classification(self, error: Exception) -> ClassificationResult:
        """Create default classification for unhandled errors."""
        return ClassificationResult(
            severity_level=ErrorSeverity.WARNING,
            error_category=ErrorCategory.UNKNOWN,
            recovery_action=RecoveryAction.USER_INTERVENTION,
            user_notification=UserNotification(
                notification_type="modal",
                title="Unexpected Error",
                message=f"An unexpected error occurred: {str(error)}",
                technical_details=traceback.format_exc(),
                suggested_actions=["Report this error", "Try again", "Restart application"],
                severity_color="#F59E0B"
            ),
            confidence_score=0.1
        )

    def _initialize_severity_rules(self) -> Dict[str, Any]:
        """Initialize severity classification rules."""
        return {
            'critical_keywords': ['memory', 'gpu', 'cuda', 'fatal', 'crash', 'system'],
            'recoverable_keywords': ['training', 'checkpoint', 'resume', 'interrupt'],
            'warning_keywords': ['warning', 'deprecated', 'performance'],
            'info_keywords': ['info', 'debug', 'trace']
        }

    def _initialize_category_rules(self) -> Dict[str, Any]:
        """Initialize category classification rules."""
        return {
            'resource_exhaustion': ['memory', 'gpu', 'vram', 'disk', 'storage', 'allocation'],
            'training_interruption': ['training', 'epoch', 'batch', 'gradient', 'loss'],
            'validation_failure': ['validation', 'invalid', 'format', 'schema'],
            'io_error': ['io', 'file', 'permission', 'access'],
            'configuration_error': ['config', 'setting', 'parameter', 'option']
        }

    def _initialize_recovery_rules(self) -> Dict[str, Any]:
        """Initialize recovery action rules."""
        return {
            'critical_actions': {
                'resource_exhaustion': RecoveryAction.CHECKPOINT_RESTORE,
                'system_failure': RecoveryAction.RESTART,
                'default': RecoveryAction.ABORT
            },
            'recoverable_actions': {
                'training_interruption': RecoveryAction.CHECKPOINT_RESTORE,
                'default': RecoveryAction.RETRY
            },
            'warning_actions': {
                'default': RecoveryAction.DEGRADE
            },
            'info_actions': {
                'default': RecoveryAction.IGNORE
            }
        }

    def get_classification_stats(self) -> Dict[str, Any]:
        """Get classification statistics."""
        with self._lock:
            return {
                'total_classifications': len(self._classification_cache),
                'cache_size': len(self._classification_cache),
                'severity_distribution': self._get_severity_distribution(),
                'category_distribution': self._get_category_distribution()
            }

    def _get_severity_distribution(self) -> Dict[str, int]:
        """Get distribution of error severities."""
        distribution = {severity.value: 0 for severity in ErrorSeverity}
        for result in self._classification_cache.values():
            distribution[result.severity_level.value] += 1
        return distribution

    def _get_category_distribution(self) -> Dict[str, int]:
        """Get distribution of error categories."""
        distribution = {category.value: 0 for category in ErrorCategory}
        for result in self._classification_cache.values():
            distribution[result.error_category.value] += 1
        return distribution

    def clear_cache(self) -> None:
        """Clear the classification cache."""
        with self._lock:
            self._classification_cache.clear()
        self._logger.info("Classification cache cleared")
