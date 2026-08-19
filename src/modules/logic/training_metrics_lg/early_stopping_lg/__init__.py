"""
Early Stopping Module
Implements early stopping logic based on validation metrics with patience tracking and improvement detection.
"""

from .early_stopping_lg import (
    EarlyStopping,
    PatienceTracker,
    ImprovementDetector,
    StoppingCriteriaEvaluator
)

__all__ = [
    'EarlyStopping',
    'PatienceTracker',
    'ImprovementDetector',
    'StoppingCriteriaEvaluator'
]
