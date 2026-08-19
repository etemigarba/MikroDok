"""
Error Classifier Module
Provides error classification and severity determination functionality.
"""

from .error_classifier_lg import (
    ErrorClassifier,
    ErrorSeverity,
    ErrorCategory,
    ErrorContext,
    RecoveryAction,
    UserNotification,
    ClassificationResult
)

__all__ = [
    'ErrorClassifier',
    'ErrorSeverity',
    'ErrorCategory',
    'ErrorContext',
    'RecoveryAction',
    'UserNotification',
    'ClassificationResult'
]
