"""
Module: loss_calculator_lg
Description: Calculates and tracks training and validation loss values with support for multiple loss functions
Phase: 4
Location: /src/modules/logic/training_metrics_lg/loss_calculator_lg/
"""

# Standard library imports
import threading
import time
from collections import deque
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable, Union
import math

# Third-party imports
import numpy as np

# Local imports
from ..base_interfaces import (
    ILossCalculator, LossType, LossConfiguration, LossResult
)
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ErrorClassifier, ErrorSeverity


class CustomLossFunction:
    """Custom loss function wrapper for user-defined loss calculations."""
    
    def __init__(
        self,
        name: str,
        loss_fn: Callable[[np.ndarray, np.ndarray], float],
        gradient_fn: Optional[Callable[[np.ndarray, np.ndarray], np.ndarray]] = None
    ):
        """
        Initialize custom loss function.
        
        Args:
            name: Name of the custom loss function
            loss_fn: Function that calculates loss
            gradient_fn: Optional gradient function
        """
        self.name = name
        self.loss_fn = loss_fn
        self.gradient_fn = gradient_fn
        self._logger = get_logger(__name__)
    
    def calculate(self, predictions: np.ndarray, targets: np.ndarray) -> float:
        """Calculate loss using custom function."""
        try:
            return float(self.loss_fn(predictions, targets))
        except Exception as e:
            self._logger.error(f"Error in custom loss function {self.name}: {e}")
            return float('inf')
    
    def calculate_gradient(
        self,
        predictions: np.ndarray,
        targets: np.ndarray
    ) -> Optional[np.ndarray]:
        """Calculate gradient if gradient function is provided."""
        if self.gradient_fn is None:
            return None
        
        try:
            return self.gradient_fn(predictions, targets)
        except Exception as e:
            self._logger.error(f"Error in gradient calculation for {self.name}: {e}")
            return None


class TrainingLossTracker:
    """Tracks training loss values with moving averages and statistics."""
    
    def __init__(self, window_size: int = 100):
        """
        Initialize training loss tracker.
        
        Args:
            window_size: Size of the moving window for statistics
        """
        self.window_size = window_size
        self._loss_history = deque(maxlen=window_size)
        self._timestamps = deque(maxlen=window_size)
        self._lock = threading.Lock()
        self._logger = get_logger(__name__)
        
        # Statistics
        self._total_loss = 0.0
        self._total_samples = 0
        self._min_loss = float('inf')
        self._max_loss = float('-inf')
    
    def add_loss(self, loss_value: float, timestamp: Optional[datetime] = None) -> None:
        """Add a loss value to the tracker."""
        if timestamp is None:
            timestamp = datetime.now()
        
        with self._lock:
            self._loss_history.append(loss_value)
            self._timestamps.append(timestamp)
            
            # Update statistics
            self._total_loss += loss_value
            self._total_samples += 1
            self._min_loss = min(self._min_loss, loss_value)
            self._max_loss = max(self._max_loss, loss_value)
    
    def get_moving_average(self, window: Optional[int] = None) -> float:
        """Get moving average of loss values."""
        if window is None:
            window = self.window_size
        
        with self._lock:
            if not self._loss_history:
                return 0.0
            
            recent_losses = list(self._loss_history)[-window:]
            return sum(recent_losses) / len(recent_losses)
    
    def get_statistics(self) -> Dict[str, float]:
        """Get comprehensive loss statistics."""
        with self._lock:
            if not self._loss_history:
                return {
                    'mean': 0.0, 'std': 0.0, 'min': 0.0, 'max': 0.0,
                    'current': 0.0, 'trend': 0.0
                }
            
            losses = np.array(self._loss_history)
            
            # Calculate trend (slope of recent losses)
            if len(losses) >= 2:
                x = np.arange(len(losses))
                trend = np.polyfit(x, losses, 1)[0]
            else:
                trend = 0.0
            
            return {
                'mean': float(np.mean(losses)),
                'std': float(np.std(losses)),
                'min': float(np.min(losses)),
                'max': float(np.max(losses)),
                'current': float(losses[-1]),
                'trend': float(trend)
            }


class ValidationLossTracker:
    """Tracks validation loss values with early stopping support."""
    
    def __init__(self, patience: int = 10, min_delta: float = 0.001):
        """
        Initialize validation loss tracker.
        
        Args:
            patience: Number of epochs to wait for improvement
            min_delta: Minimum change to qualify as improvement
        """
        self.patience = patience
        self.min_delta = min_delta
        self._loss_history = []
        self._timestamps = []
        self._lock = threading.Lock()
        self._logger = get_logger(__name__)
        
        # Early stopping state
        self._best_loss = float('inf')
        self._best_epoch = 0
        self._patience_counter = 0
        self._should_stop = False
    
    def add_validation_loss(
        self,
        loss_value: float,
        epoch: int,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Add validation loss and check for early stopping.
        
        Returns:
            True if training should stop early
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        with self._lock:
            self._loss_history.append(loss_value)
            self._timestamps.append(timestamp)
            
            # Check for improvement
            if loss_value < self._best_loss - self.min_delta:
                self._best_loss = loss_value
                self._best_epoch = epoch
                self._patience_counter = 0
                self._logger.info(f"Validation loss improved to {loss_value:.6f}")
            else:
                self._patience_counter += 1
                self._logger.debug(f"No improvement in validation loss. Patience: {self._patience_counter}/{self.patience}")
            
            # Check early stopping
            if self._patience_counter >= self.patience:
                self._should_stop = True
                self._logger.info(f"Early stopping triggered. Best loss: {self._best_loss:.6f} at epoch {self._best_epoch}")
            
            return self._should_stop
    
    def reset(self) -> None:
        """Reset early stopping state."""
        with self._lock:
            self._best_loss = float('inf')
            self._best_epoch = 0
            self._patience_counter = 0
            self._should_stop = False
    
    def get_best_loss(self) -> float:
        """Get the best validation loss seen so far."""
        with self._lock:
            return self._best_loss


class LossCalculator(ILossCalculator):
    """Main loss calculator with support for multiple loss functions."""
    
    def __init__(self):
        """Initialize loss calculator."""
        self._logger = get_logger(__name__)
        self._error_classifier = ErrorClassifier()
        self._custom_functions: Dict[str, CustomLossFunction] = {}
        self._lock = threading.Lock()
        
        # Performance tracking
        self._calculation_times = deque(maxlen=1000)
        self._total_calculations = 0
    
    def register_custom_function(self, custom_fn: CustomLossFunction) -> None:
        """Register a custom loss function."""
        with self._lock:
            self._custom_functions[custom_fn.name] = custom_fn
            self._logger.info(f"Registered custom loss function: {custom_fn.name}")
    
    def calculate_loss(
        self,
        predictions: np.ndarray,
        targets: np.ndarray,
        config: LossConfiguration
    ) -> LossResult:
        """Calculate loss between predictions and targets."""
        start_time = time.time()
        
        try:
            # Validate inputs
            self._validate_inputs(predictions, targets)
            
            # Calculate loss based on type
            if config.loss_type == LossType.CROSS_ENTROPY:
                loss_value = self._calculate_cross_entropy(predictions, targets, config)
            elif config.loss_type == LossType.MSE:
                loss_value = self._calculate_mse(predictions, targets, config)
            elif config.loss_type == LossType.MAE:
                loss_value = self._calculate_mae(predictions, targets, config)
            elif config.loss_type == LossType.HUBER:
                loss_value = self._calculate_huber(predictions, targets, config)
            elif config.loss_type == LossType.FOCAL:
                loss_value = self._calculate_focal(predictions, targets, config)
            elif config.loss_type == LossType.CUSTOM:
                loss_value = self._calculate_custom(predictions, targets, config)
            else:
                raise ValueError(f"Unsupported loss type: {config.loss_type}")
            
            # Track performance
            calculation_time = (time.time() - start_time) * 1000
            with self._lock:
                self._calculation_times.append(calculation_time)
                self._total_calculations += 1
            
            return LossResult(
                loss_value=loss_value,
                loss_type=config.loss_type,
                batch_size=len(predictions),
                timestamp=datetime.now(),
                metadata={
                    'calculation_time_ms': calculation_time,
                    'reduction': config.reduction,
                    'label_smoothing': config.label_smoothing
                }
            )
            
        except Exception as e:
            self._logger.error(f"Error calculating loss: {e}")
            classification = self._error_classifier.classify_error(e)
            
            return LossResult(
                loss_value=float('inf'),
                loss_type=config.loss_type,
                batch_size=len(predictions) if predictions is not None else 0,
                timestamp=datetime.now(),
                metadata={
                    'error': str(e),
                    'error_severity': classification.severity.value
                }
            )

    def calculate_batch_loss(
        self,
        batch_predictions: List[np.ndarray],
        batch_targets: List[np.ndarray],
        config: LossConfiguration
    ) -> List[LossResult]:
        """Calculate loss for multiple batches."""
        try:
            if len(batch_predictions) != len(batch_targets):
                raise ValueError("Batch predictions and targets must have same length")

            results = []
            for predictions, targets in zip(batch_predictions, batch_targets):
                result = self.calculate_loss(predictions, targets, config)
                results.append(result)

            return results

        except Exception as e:
            self._logger.error(f"Error calculating batch loss: {e}")
            return []

    def _validate_inputs(self, predictions: np.ndarray, targets: np.ndarray) -> None:
        """Validate input arrays."""
        if predictions is None or targets is None:
            raise ValueError("Predictions and targets cannot be None")

        if predictions.shape != targets.shape:
            raise ValueError(f"Shape mismatch: predictions {predictions.shape} vs targets {targets.shape}")

        if len(predictions) == 0:
            raise ValueError("Empty input arrays")

    def _calculate_cross_entropy(
        self,
        predictions: np.ndarray,
        targets: np.ndarray,
        config: LossConfiguration
    ) -> float:
        """Calculate cross-entropy loss."""
        # Apply label smoothing if specified
        if config.label_smoothing > 0:
            num_classes = predictions.shape[-1]
            targets = targets * (1 - config.label_smoothing) + config.label_smoothing / num_classes

        # Clip predictions to prevent log(0)
        predictions = np.clip(predictions, 1e-15, 1 - 1e-15)

        # Calculate cross-entropy
        if targets.ndim == 1:  # Sparse targets
            loss = -np.log(predictions[np.arange(len(targets)), targets.astype(int)])
        else:  # One-hot targets
            loss = -np.sum(targets * np.log(predictions), axis=-1)

        # Apply reduction
        if config.reduction == "mean":
            return float(np.mean(loss))
        elif config.reduction == "sum":
            return float(np.sum(loss))
        else:
            return loss

    def _calculate_mse(
        self,
        predictions: np.ndarray,
        targets: np.ndarray,
        config: LossConfiguration
    ) -> float:
        """Calculate mean squared error loss."""
        loss = (predictions - targets) ** 2

        if config.reduction == "mean":
            return float(np.mean(loss))
        elif config.reduction == "sum":
            return float(np.sum(loss))
        else:
            return loss

    def _calculate_mae(
        self,
        predictions: np.ndarray,
        targets: np.ndarray,
        config: LossConfiguration
    ) -> float:
        """Calculate mean absolute error loss."""
        loss = np.abs(predictions - targets)

        if config.reduction == "mean":
            return float(np.mean(loss))
        elif config.reduction == "sum":
            return float(np.sum(loss))
        else:
            return loss

    def _calculate_huber(
        self,
        predictions: np.ndarray,
        targets: np.ndarray,
        config: LossConfiguration
    ) -> float:
        """Calculate Huber loss."""
        delta = config.custom_params.get('delta', 1.0)
        diff = np.abs(predictions - targets)

        # Huber loss formula
        loss = np.where(
            diff <= delta,
            0.5 * diff ** 2,
            delta * (diff - 0.5 * delta)
        )

        if config.reduction == "mean":
            return float(np.mean(loss))
        elif config.reduction == "sum":
            return float(np.sum(loss))
        else:
            return loss

    def _calculate_focal(
        self,
        predictions: np.ndarray,
        targets: np.ndarray,
        config: LossConfiguration
    ) -> float:
        """Calculate focal loss."""
        alpha = config.custom_params.get('alpha', 1.0)
        gamma = config.custom_params.get('gamma', 2.0)

        # Clip predictions
        predictions = np.clip(predictions, 1e-15, 1 - 1e-15)

        # Calculate focal loss
        if targets.ndim == 1:  # Sparse targets
            ce_loss = -np.log(predictions[np.arange(len(targets)), targets.astype(int)])
            pt = predictions[np.arange(len(targets)), targets.astype(int)]
        else:  # One-hot targets
            ce_loss = -np.sum(targets * np.log(predictions), axis=-1)
            pt = np.sum(targets * predictions, axis=-1)

        focal_weight = alpha * (1 - pt) ** gamma
        loss = focal_weight * ce_loss

        if config.reduction == "mean":
            return float(np.mean(loss))
        elif config.reduction == "sum":
            return float(np.sum(loss))
        else:
            return loss

    def _calculate_custom(
        self,
        predictions: np.ndarray,
        targets: np.ndarray,
        config: LossConfiguration
    ) -> float:
        """Calculate custom loss using registered function."""
        function_name = config.custom_params.get('function_name')
        if not function_name:
            raise ValueError("Custom loss requires 'function_name' in custom_params")

        with self._lock:
            if function_name not in self._custom_functions:
                raise ValueError(f"Custom loss function '{function_name}' not registered")

            custom_fn = self._custom_functions[function_name]

        return custom_fn.calculate(predictions, targets)

    def get_performance_stats(self) -> Dict[str, float]:
        """Get performance statistics for loss calculations."""
        with self._lock:
            if not self._calculation_times:
                return {
                    'avg_calculation_time_ms': 0.0,
                    'min_calculation_time_ms': 0.0,
                    'max_calculation_time_ms': 0.0,
                    'total_calculations': 0
                }

            times = np.array(self._calculation_times)
            return {
                'avg_calculation_time_ms': float(np.mean(times)),
                'min_calculation_time_ms': float(np.min(times)),
                'max_calculation_time_ms': float(np.max(times)),
                'total_calculations': self._total_calculations
            }
