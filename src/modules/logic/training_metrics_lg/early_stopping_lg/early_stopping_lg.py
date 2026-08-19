"""
Module: early_stopping_lg
Description: Implements early stopping logic based on validation metrics with patience tracking and improvement detection
Phase: 4
Location: /src/modules/logic/training_metrics_lg/early_stopping_lg/
"""

# Standard library imports
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable, Union
import math

# Third-party imports
import numpy as np

# Local imports
from ..base_interfaces import (
    IEarlyStopping, EarlyStoppingCriteria, EarlyStoppingConfiguration,
    EarlyStoppingResult, MetricResult
)
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ErrorClassifier, ErrorSeverity


class ImprovementDetector:
    """Detects improvements in training metrics with configurable sensitivity."""
    
    def __init__(
        self,
        min_delta: float = 0.001,
        mode: str = "min",
        relative_threshold: bool = False
    ):
        """
        Initialize improvement detector.
        
        Args:
            min_delta: Minimum change to qualify as improvement
            mode: "min" for loss-like metrics, "max" for accuracy-like metrics
            relative_threshold: Whether to use relative or absolute threshold
        """
        self.min_delta = min_delta
        self.mode = mode.lower()
        self.relative_threshold = relative_threshold
        self._logger = get_logger(__name__)
        
        if self.mode not in ["min", "max"]:
            raise ValueError("Mode must be 'min' or 'max'")
    
    def is_improvement(self, current_value: float, best_value: float) -> bool:
        """
        Check if current value represents an improvement.
        
        Args:
            current_value: Current metric value
            best_value: Best metric value seen so far
            
        Returns:
            True if current value is an improvement
        """
        try:
            if math.isnan(current_value) or math.isinf(current_value):
                return False
            
            if math.isnan(best_value) or math.isinf(best_value):
                return True
            
            # Calculate threshold
            if self.relative_threshold:
                threshold = abs(best_value) * self.min_delta
            else:
                threshold = self.min_delta
            
            # Check improvement based on mode
            if self.mode == "min":
                return current_value < (best_value - threshold)
            else:  # mode == "max"
                return current_value > (best_value + threshold)
                
        except Exception as e:
            self._logger.error(f"Error detecting improvement: {e}")
            return False
    
    def calculate_improvement(self, current_value: float, best_value: float) -> float:
        """
        Calculate the amount of improvement.
        
        Args:
            current_value: Current metric value
            best_value: Best metric value seen so far
            
        Returns:
            Improvement amount (positive for improvement, negative for degradation)
        """
        try:
            if math.isnan(current_value) or math.isnan(best_value):
                return 0.0
            
            if self.mode == "min":
                return best_value - current_value
            else:  # mode == "max"
                return current_value - best_value
                
        except Exception as e:
            self._logger.error(f"Error calculating improvement: {e}")
            return 0.0


class PatienceTracker:
    """Tracks patience for early stopping with advanced patience strategies."""
    
    def __init__(
        self,
        patience: int = 10,
        adaptive_patience: bool = False,
        patience_factor: float = 1.5,
        max_patience: int = 100
    ):
        """
        Initialize patience tracker.
        
        Args:
            patience: Initial patience value
            adaptive_patience: Whether to use adaptive patience
            patience_factor: Factor for adaptive patience increase
            max_patience: Maximum patience value for adaptive mode
        """
        self.initial_patience = patience
        self.adaptive_patience = adaptive_patience
        self.patience_factor = patience_factor
        self.max_patience = max_patience
        
        self._current_patience = patience
        self._patience_counter = 0
        self._improvement_history = deque(maxlen=100)
        self._lock = threading.Lock()
        self._logger = get_logger(__name__)
    
    def update(self, is_improvement: bool, improvement_amount: float = 0.0) -> int:
        """
        Update patience counter and return current patience.
        
        Args:
            is_improvement: Whether there was an improvement
            improvement_amount: Amount of improvement
            
        Returns:
            Current patience counter
        """
        with self._lock:
            if is_improvement:
                self._patience_counter = 0
                self._improvement_history.append(improvement_amount)
                
                # Adaptive patience adjustment
                if self.adaptive_patience:
                    self._adjust_adaptive_patience()
                
                self._logger.debug(f"Improvement detected. Patience reset. Current patience: {self._current_patience}")
            else:
                self._patience_counter += 1
                self._improvement_history.append(0.0)
                self._logger.debug(f"No improvement. Patience counter: {self._patience_counter}/{self._current_patience}")
            
            return self._patience_counter
    
    def should_stop(self) -> bool:
        """Check if early stopping should be triggered."""
        with self._lock:
            return self._patience_counter >= self._current_patience
    
    def reset(self) -> None:
        """Reset patience tracker."""
        with self._lock:
            self._current_patience = self.initial_patience
            self._patience_counter = 0
            self._improvement_history.clear()
            self._logger.info("Patience tracker reset")
    
    def get_patience_info(self) -> Dict[str, Any]:
        """Get current patience information."""
        with self._lock:
            return {
                'current_patience': self._current_patience,
                'patience_counter': self._patience_counter,
                'remaining_patience': max(0, self._current_patience - self._patience_counter),
                'patience_ratio': self._patience_counter / max(1, self._current_patience),
                'adaptive_patience_enabled': self.adaptive_patience,
                'recent_improvements': len([x for x in self._improvement_history if x > 0])
            }
    
    def _adjust_adaptive_patience(self) -> None:
        """Adjust patience based on improvement history."""
        if len(self._improvement_history) < 10:
            return
        
        # Calculate improvement rate
        recent_improvements = [x for x in list(self._improvement_history)[-10:] if x > 0]
        improvement_rate = len(recent_improvements) / 10.0
        
        # Adjust patience based on improvement rate
        if improvement_rate > 0.3:  # High improvement rate
            new_patience = min(
                self.max_patience,
                int(self._current_patience * self.patience_factor)
            )
            if new_patience != self._current_patience:
                self._logger.info(f"Adaptive patience increased from {self._current_patience} to {new_patience}")
                self._current_patience = new_patience


class StoppingCriteriaEvaluator:
    """Evaluates complex stopping criteria with multiple metrics."""
    
    def __init__(self):
        """Initialize stopping criteria evaluator."""
        self._criteria_functions: Dict[str, Callable] = {}
        self._metric_history: Dict[str, deque] = {}
        self._lock = threading.Lock()
        self._logger = get_logger(__name__)
    
    def register_criteria(self, name: str, criteria_fn: Callable[[List[float]], bool]) -> None:
        """
        Register a custom stopping criteria function.
        
        Args:
            name: Name of the criteria
            criteria_fn: Function that takes metric history and returns bool
        """
        with self._lock:
            self._criteria_functions[name] = criteria_fn
            self._logger.info(f"Registered stopping criteria: {name}")
    
    def add_metric_value(self, metric_name: str, value: float) -> None:
        """Add a metric value to the history."""
        with self._lock:
            if metric_name not in self._metric_history:
                self._metric_history[metric_name] = deque(maxlen=1000)
            
            self._metric_history[metric_name].append(value)
    
    def evaluate_criteria(self, criteria_name: str, metric_name: str) -> bool:
        """
        Evaluate a specific stopping criteria.
        
        Args:
            criteria_name: Name of the criteria to evaluate
            metric_name: Name of the metric to use
            
        Returns:
            True if stopping criteria is met
        """
        try:
            with self._lock:
                if criteria_name not in self._criteria_functions:
                    self._logger.warning(f"Unknown criteria: {criteria_name}")
                    return False
                
                if metric_name not in self._metric_history:
                    return False
                
                metric_values = list(self._metric_history[metric_name])
                criteria_fn = self._criteria_functions[criteria_name]
                
                return criteria_fn(metric_values)
                
        except Exception as e:
            self._logger.error(f"Error evaluating criteria {criteria_name}: {e}")
            return False
    
    def evaluate_combined_criteria(
        self,
        criteria_configs: List[Dict[str, str]],
        combination_mode: str = "any"
    ) -> bool:
        """
        Evaluate multiple criteria with combination logic.
        
        Args:
            criteria_configs: List of criteria configurations
            combination_mode: "any", "all", or "majority"
            
        Returns:
            True if combined criteria is met
        """
        try:
            results = []
            
            for config in criteria_configs:
                criteria_name = config.get('criteria_name')
                metric_name = config.get('metric_name')
                
                if criteria_name and metric_name:
                    result = self.evaluate_criteria(criteria_name, metric_name)
                    results.append(result)
            
            if not results:
                return False
            
            if combination_mode == "any":
                return any(results)
            elif combination_mode == "all":
                return all(results)
            elif combination_mode == "majority":
                return sum(results) > len(results) / 2
            else:
                self._logger.warning(f"Unknown combination mode: {combination_mode}")
                return any(results)
                
        except Exception as e:
            self._logger.error(f"Error evaluating combined criteria: {e}")
            return False


class EarlyStopping(IEarlyStopping):
    """Main early stopping implementation with comprehensive stopping logic."""
    
    def __init__(self, config: EarlyStoppingConfiguration):
        """
        Initialize early stopping.
        
        Args:
            config: Early stopping configuration
        """
        self.config = config
        self._logger = get_logger(__name__)
        self._error_classifier = ErrorClassifier()
        
        # Initialize components
        self._improvement_detector = ImprovementDetector(
            min_delta=config.min_delta,
            mode=config.mode,
            relative_threshold=config.custom_params.get('relative_threshold', False)
        )
        
        self._patience_tracker = PatienceTracker(
            patience=config.patience,
            adaptive_patience=config.custom_params.get('adaptive_patience', False),
            patience_factor=config.custom_params.get('patience_factor', 1.5),
            max_patience=config.custom_params.get('max_patience', 100)
        )
        
        self._criteria_evaluator = StoppingCriteriaEvaluator()
        
        # State tracking
        self._best_value = float('inf') if config.mode == "min" else float('-inf')
        self._best_epoch = 0
        self._history = deque(maxlen=1000)
        self._lock = threading.Lock()
        
        # Register default criteria
        self._register_default_criteria()
    
    def update(self, current_value: float, epoch: int) -> EarlyStoppingResult:
        """Update early stopping with current metric value."""
        try:
            with self._lock:
                # Add to history
                self._history.append((epoch, current_value, datetime.now()))
                self._criteria_evaluator.add_metric_value(
                    self.config.criteria.value, current_value
                )
                
                # Check for improvement
                is_improvement = self._improvement_detector.is_improvement(
                    current_value, self._best_value
                )
                
                improvement_amount = self._improvement_detector.calculate_improvement(
                    current_value, self._best_value
                )
                
                # Update best value if improved
                if is_improvement:
                    self._best_value = current_value
                    self._best_epoch = epoch
                
                # Update patience
                patience_counter = self._patience_tracker.update(
                    is_improvement, improvement_amount
                )
                
                # Check stopping criteria
                should_stop = self._should_stop_training(current_value)
                
                return EarlyStoppingResult(
                    should_stop=should_stop,
                    current_patience=patience_counter,
                    best_value=self._best_value,
                    improvement=improvement_amount,
                    criteria=self.config.criteria,
                    timestamp=datetime.now(),
                    metadata={
                        'epoch': epoch,
                        'current_value': current_value,
                        'is_improvement': is_improvement,
                        'patience_info': self._patience_tracker.get_patience_info(),
                        'best_epoch': self._best_epoch
                    }
                )
                
        except Exception as e:
            self._logger.error(f"Error updating early stopping: {e}")
            classification = self._error_classifier.classify_error(e)
            
            return EarlyStoppingResult(
                should_stop=False,
                current_patience=0,
                best_value=self._best_value,
                improvement=0.0,
                criteria=self.config.criteria,
                timestamp=datetime.now(),
                metadata={
                    'error': str(e),
                    'error_severity': classification.severity.value
                }
            )

    def reset(self) -> None:
        """Reset early stopping state."""
        with self._lock:
            self._best_value = float('inf') if self.config.mode == "min" else float('-inf')
            self._best_epoch = 0
            self._history.clear()
            self._patience_tracker.reset()

            # Clear criteria evaluator history
            self._criteria_evaluator._metric_history.clear()

            self._logger.info("Early stopping state reset")

    def get_best_value(self) -> float:
        """Get the best metric value seen so far."""
        with self._lock:
            return self._best_value

    def _should_stop_training(self, current_value: float) -> bool:
        """Determine if training should stop based on all criteria."""
        # Check patience-based stopping
        if self._patience_tracker.should_stop():
            return True

        # Check baseline criteria if configured
        if self.config.baseline is not None:
            if self.config.mode == "min" and current_value <= self.config.baseline:
                return True
            elif self.config.mode == "max" and current_value >= self.config.baseline:
                return True

        # Check custom criteria if configured
        custom_criteria = self.config.custom_params.get('custom_criteria', [])
        if custom_criteria:
            combination_mode = self.config.custom_params.get('combination_mode', 'any')
            if self._criteria_evaluator.evaluate_combined_criteria(
                custom_criteria, combination_mode
            ):
                return True

        return False

    def _register_default_criteria(self) -> None:
        """Register default stopping criteria functions."""

        def plateau_criteria(values: List[float]) -> bool:
            """Stop if metric has plateaued for too long."""
            if len(values) < 20:
                return False

            recent_values = values[-20:]
            std_dev = np.std(recent_values)
            threshold = self.config.min_delta * 10  # 10x the improvement threshold

            return std_dev < threshold

        def divergence_criteria(values: List[float]) -> bool:
            """Stop if metric is diverging (getting worse rapidly)."""
            if len(values) < 10:
                return False

            recent_values = values[-10:]
            if self.config.mode == "min":
                # For loss-like metrics, check if increasing rapidly
                trend = np.polyfit(range(len(recent_values)), recent_values, 1)[0]
                return trend > self.config.min_delta * 5
            else:
                # For accuracy-like metrics, check if decreasing rapidly
                trend = np.polyfit(range(len(recent_values)), recent_values, 1)[0]
                return trend < -self.config.min_delta * 5

        def oscillation_criteria(values: List[float]) -> bool:
            """Stop if metric is oscillating without clear improvement."""
            if len(values) < 30:
                return False

            recent_values = values[-30:]

            # Count direction changes
            direction_changes = 0
            for i in range(1, len(recent_values)):
                if i > 1:
                    prev_diff = recent_values[i-1] - recent_values[i-2]
                    curr_diff = recent_values[i] - recent_values[i-1]
                    if (prev_diff > 0) != (curr_diff > 0):
                        direction_changes += 1

            # If more than 50% direction changes, consider it oscillating
            return direction_changes > len(recent_values) * 0.5

        # Register criteria
        self._criteria_evaluator.register_criteria('plateau', plateau_criteria)
        self._criteria_evaluator.register_criteria('divergence', divergence_criteria)
        self._criteria_evaluator.register_criteria('oscillation', oscillation_criteria)

    def get_stopping_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary of early stopping state."""
        with self._lock:
            history_values = [val for _, val, _ in self._history]

            summary = {
                'best_value': self._best_value,
                'best_epoch': self._best_epoch,
                'current_patience': self._patience_tracker.get_patience_info(),
                'criteria': self.config.criteria.value,
                'mode': self.config.mode,
                'min_delta': self.config.min_delta,
                'baseline': self.config.baseline,
                'history_length': len(self._history),
                'recent_trend': None,
                'stopping_probability': 0.0
            }

            # Calculate recent trend
            if len(history_values) >= 5:
                recent_values = history_values[-5:]
                trend = np.polyfit(range(len(recent_values)), recent_values, 1)[0]
                summary['recent_trend'] = float(trend)

            # Calculate stopping probability based on patience ratio
            patience_info = self._patience_tracker.get_patience_info()
            summary['stopping_probability'] = patience_info['patience_ratio']

            return summary

    def export_history(self) -> List[Dict[str, Any]]:
        """Export the complete history of metric values."""
        with self._lock:
            return [
                {
                    'epoch': epoch,
                    'value': value,
                    'timestamp': timestamp.isoformat(),
                    'is_best': value == self._best_value
                }
                for epoch, value, timestamp in self._history
            ]
