"""
Module: usage_predictor_lg
Description: ML-based prediction of future resource requirements using LSTM networks and historical usage patterns
Phase: 2
Location: /src/modules/logic/resource_predictor_lg/usage_predictor_lg/
"""

# Standard library imports
import asyncio
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Union
import json
import math

# Third-party imports
import numpy as np
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# Local imports
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import ValidationEngine
from src.modules.logic.resource_monitor_lg import (
    ResourceMetrics, 
    GPUMetrics, 
    MemoryMetrics, 
    DiskMetrics, 
    ThermalMetrics
)


class PredictionModel(Enum):
    """Available prediction models."""
    LSTM = "LSTM"
    LINEAR_REGRESSION = "LINEAR_REGRESSION"
    MOVING_AVERAGE = "MOVING_AVERAGE"
    EXPONENTIAL_SMOOTHING = "EXPONENTIAL_SMOOTHING"


class ResourceType(Enum):
    """Resource types for prediction."""
    CPU = "CPU"
    MEMORY = "MEMORY"
    GPU = "GPU"
    DISK = "DISK"
    THERMAL = "THERMAL"


@dataclass
class TimeSeriesData:
    """Time series data for resource usage."""
    timestamps: List[datetime]
    values: List[float]
    resource_type: ResourceType
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate time series data."""
        if len(self.timestamps) != len(self.values):
            raise ValueError("Timestamps and values must have the same length")
        if len(self.timestamps) == 0:
            raise ValueError("Time series data cannot be empty")


@dataclass
class ResourcePrediction:
    """Resource usage prediction result."""
    resource_type: ResourceType
    predicted_values: List[float]
    prediction_timestamps: List[datetime]
    confidence_intervals: List[Tuple[float, float]]
    model_used: PredictionModel
    accuracy_score: float
    prediction_horizon_minutes: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PredictionMetrics:
    """Metrics for prediction model performance."""
    mae: float  # Mean Absolute Error
    mse: float  # Mean Squared Error
    rmse: float  # Root Mean Squared Error
    mape: float  # Mean Absolute Percentage Error
    r2_score: float  # R-squared score
    prediction_accuracy: float
    model_confidence: float


@dataclass
class PredictionConfiguration:
    """Configuration for usage prediction."""
    prediction_horizon_minutes: int = 30
    historical_window_hours: int = 24
    sampling_interval_seconds: int = 60
    model_type: PredictionModel = PredictionModel.LSTM
    confidence_level: float = 0.95
    retrain_interval_hours: int = 6
    min_data_points: int = 100
    enable_gpu_acceleration: bool = True
    lstm_hidden_size: int = 64
    lstm_num_layers: int = 2
    learning_rate: float = 0.001
    batch_size: int = 32
    epochs: int = 100


class IResourcePredictor(ABC):
    """Interface for resource usage predictors."""
    
    @abstractmethod
    async def predict_usage(
        self, 
        resource_type: ResourceType, 
        horizon_minutes: int = 30
    ) -> ResourcePrediction:
        """Predict future resource usage."""
        pass
    
    @abstractmethod
    def add_data_point(self, metrics: ResourceMetrics) -> None:
        """Add new data point to the prediction model."""
        pass
    
    @abstractmethod
    def get_prediction_accuracy(self, resource_type: ResourceType) -> PredictionMetrics:
        """Get prediction accuracy metrics."""
        pass
    
    @abstractmethod
    async def retrain_model(self, resource_type: ResourceType) -> bool:
        """Retrain the prediction model."""
        pass


class LSTMPredictor(nn.Module):
    """LSTM neural network for time series prediction."""
    
    def __init__(self, input_size: int = 1, hidden_size: int = 64, num_layers: int = 2, output_size: int = 1):
        """Initialize LSTM predictor."""
        super(LSTMPredictor, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.linear = nn.Linear(hidden_size, output_size)
        self.dropout = nn.Dropout(0.2)
        
    def forward(self, x):
        """Forward pass through the network."""
        # Initialize hidden state
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        
        # LSTM forward pass
        out, _ = self.lstm(x, (h0, c0))
        
        # Take the last output
        out = self.dropout(out[:, -1, :])
        out = self.linear(out)
        
        return out


class UsagePredictor(IResourcePredictor):
    """ML-based resource usage predictor with LSTM networks."""
    
    def __init__(self, 
                 config: Optional[PredictionConfiguration] = None,
                 app_state_manager: Optional[AppStateManager] = None):
        """Initialize the usage predictor."""
        self._config = config or PredictionConfiguration()
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("usage_predictor")
        self._validation_engine = ValidationEngine()
        
        # Data storage
        self._lock = threading.RLock()
        self._time_series_data: Dict[ResourceType, TimeSeriesData] = {}
        self._models: Dict[ResourceType, Any] = {}
        self._prediction_cache: Dict[str, ResourcePrediction] = {}
        self._metrics_cache: Dict[ResourceType, PredictionMetrics] = {}
        
        # Training state
        self._last_retrain: Dict[ResourceType, datetime] = {}
        self._training_in_progress: Dict[ResourceType, bool] = {}
        
        # Initialize data buffers
        self._data_buffers: Dict[ResourceType, deque] = {
            resource_type: deque(maxlen=self._config.historical_window_hours * 3600 // self._config.sampling_interval_seconds)
            for resource_type in ResourceType
        }
        
        self._logger.info("Usage predictor initialized with LSTM models")
    
    async def predict_usage(
        self, 
        resource_type: ResourceType, 
        horizon_minutes: int = 30
    ) -> ResourcePrediction:
        """
        Predict future resource usage using trained models.
        
        Args:
            resource_type: Type of resource to predict
            horizon_minutes: Prediction horizon in minutes
            
        Returns:
            Resource usage prediction
            
        Raises:
            ValueError: If insufficient data or invalid parameters
        """
        try:
            # Validate inputs
            validation_rules = [
                (horizon_minutes > 0, "Prediction horizon must be positive"),
                (horizon_minutes <= 1440, "Prediction horizon cannot exceed 24 hours"),
                (resource_type in ResourceType, "Invalid resource type")
            ]
            
            for condition, message in validation_rules:
                if not condition:
                    raise ValueError(message)
            
            # Check cache first
            cache_key = f"{resource_type.value}_{horizon_minutes}"
            with self._lock:
                if cache_key in self._prediction_cache:
                    cached_prediction = self._prediction_cache[cache_key]
                    # Check if cache is still valid (within 5 minutes)
                    if (datetime.now(timezone.utc) - cached_prediction.prediction_timestamps[0]).total_seconds() < 300:
                        return cached_prediction
            
            # Get historical data
            time_series = await self._get_time_series_data(resource_type)
            if len(time_series.values) < self._config.min_data_points:
                raise ValueError(f"Insufficient data points for {resource_type.value}: {len(time_series.values)} < {self._config.min_data_points}")
            
            # Generate prediction
            prediction = await self._generate_prediction(time_series, horizon_minutes)
            
            # Cache the prediction
            with self._lock:
                self._prediction_cache[cache_key] = prediction
            
            self._logger.info(f"Generated prediction for {resource_type.value} with {prediction.accuracy_score:.3f} accuracy")
            return prediction
            
        except Exception as e:
            self._logger.error(f"Error predicting usage for {resource_type.value}: {e}")
            raise
    
    def add_data_point(self, metrics: ResourceMetrics) -> None:
        """
        Add new resource metrics data point.
        
        Args:
            metrics: Resource metrics to add
        """
        try:
            with self._lock:
                timestamp = metrics.timestamp
                
                # Add CPU data
                self._data_buffers[ResourceType.CPU].append((timestamp, metrics.cpu_usage_percent))
                
                # Add memory data
                self._data_buffers[ResourceType.MEMORY].append((timestamp, metrics.memory_usage_percent))
                
                # Add disk data if available
                if hasattr(metrics, 'disk_usage_percent'):
                    self._data_buffers[ResourceType.DISK].append((timestamp, metrics.disk_usage_percent))
                
                # Add GPU data if available
                if hasattr(metrics, 'gpu_usage_percent'):
                    self._data_buffers[ResourceType.GPU].append((timestamp, metrics.gpu_usage_percent))
                
                # Add thermal data if available
                if hasattr(metrics, 'temperature_celsius'):
                    self._data_buffers[ResourceType.THERMAL].append((timestamp, metrics.temperature_celsius))
            
            # Check if retraining is needed (schedule in background)
            asyncio.create_task(self._check_retrain_schedule())
            
        except Exception as e:
            self._logger.error(f"Error adding data point: {e}")
    
    def get_prediction_accuracy(self, resource_type: ResourceType) -> PredictionMetrics:
        """
        Get prediction accuracy metrics for a resource type.
        
        Args:
            resource_type: Resource type to get metrics for
            
        Returns:
            Prediction accuracy metrics
        """
        with self._lock:
            if resource_type in self._metrics_cache:
                return self._metrics_cache[resource_type]
            
            # Return default metrics if no data available
            return PredictionMetrics(
                mae=0.0,
                mse=0.0,
                rmse=0.0,
                mape=0.0,
                r2_score=0.0,
                prediction_accuracy=0.0,
                model_confidence=0.0
            )
    
    async def retrain_model(self, resource_type: ResourceType) -> bool:
        """
        Retrain the prediction model for a specific resource type.
        
        Args:
            resource_type: Resource type to retrain
            
        Returns:
            True if retraining was successful
        """
        try:
            with self._lock:
                if self._training_in_progress.get(resource_type, False):
                    self._logger.warning(f"Training already in progress for {resource_type.value}")
                    return False
                
                self._training_in_progress[resource_type] = True
            
            self._logger.info(f"Starting model retraining for {resource_type.value}")
            
            # Get training data
            time_series = await self._get_time_series_data(resource_type)
            if len(time_series.values) < self._config.min_data_points:
                self._logger.warning(f"Insufficient data for retraining {resource_type.value}")
                return False
            
            # Train model based on configuration
            success = False
            if self._config.model_type == PredictionModel.LSTM and TORCH_AVAILABLE:
                success = await self._train_lstm_model(resource_type, time_series)
            else:
                success = await self._train_fallback_model(resource_type, time_series)
            
            if success:
                with self._lock:
                    self._last_retrain[resource_type] = datetime.now(timezone.utc)
                self._logger.info(f"Model retraining completed for {resource_type.value}")
            
            return success
            
        except Exception as e:
            self._logger.error(f"Error retraining model for {resource_type.value}: {e}")
            return False
        finally:
            with self._lock:
                self._training_in_progress[resource_type] = False

    async def _get_time_series_data(self, resource_type: ResourceType) -> TimeSeriesData:
        """Get time series data for a resource type."""
        with self._lock:
            buffer = self._data_buffers[resource_type]
            if not buffer:
                raise ValueError(f"No data available for {resource_type.value}")

            timestamps, values = zip(*buffer)
            return TimeSeriesData(
                timestamps=list(timestamps),
                values=list(values),
                resource_type=resource_type
            )

    async def _generate_prediction(self, time_series: TimeSeriesData, horizon_minutes: int) -> ResourcePrediction:
        """Generate prediction using the appropriate model."""
        resource_type = time_series.resource_type

        # Use trained model if available
        with self._lock:
            model = self._models.get(resource_type)

        if model and self._config.model_type == PredictionModel.LSTM and TORCH_AVAILABLE:
            return await self._predict_with_lstm(model, time_series, horizon_minutes)
        else:
            return await self._predict_with_fallback(time_series, horizon_minutes)

    async def _predict_with_lstm(self, model: LSTMPredictor, time_series: TimeSeriesData, horizon_minutes: int) -> ResourcePrediction:
        """Generate prediction using LSTM model."""
        try:
            # Prepare data
            values = np.array(time_series.values, dtype=np.float32)
            values = (values - values.mean()) / (values.std() + 1e-8)  # Normalize

            # Create sequences
            sequence_length = min(60, len(values) // 2)  # Use last hour or half the data
            if len(values) < sequence_length:
                sequence_length = len(values)

            input_sequence = values[-sequence_length:].reshape(1, sequence_length, 1)
            input_tensor = torch.FloatTensor(input_sequence)

            # Generate predictions
            model.eval()
            predictions = []
            current_sequence = input_tensor.clone()

            prediction_steps = horizon_minutes // (self._config.sampling_interval_seconds // 60)

            with torch.no_grad():
                for _ in range(prediction_steps):
                    pred = model(current_sequence)
                    predictions.append(pred.item())

                    # Update sequence for next prediction
                    new_sequence = torch.cat([current_sequence[:, 1:, :], pred.unsqueeze(0).unsqueeze(2)], dim=1)
                    current_sequence = new_sequence

            # Denormalize predictions
            mean_val = np.mean(time_series.values)
            std_val = np.std(time_series.values) + 1e-8
            predictions = [p * std_val + mean_val for p in predictions]

            # Ensure predictions are within reasonable bounds
            predictions = [max(0, min(100, p)) for p in predictions]

            # Generate timestamps
            start_time = time_series.timestamps[-1]
            prediction_timestamps = [
                start_time + timedelta(minutes=i * (self._config.sampling_interval_seconds // 60))
                for i in range(1, len(predictions) + 1)
            ]

            # Calculate confidence intervals (simplified)
            confidence_intervals = [(max(0, p - 5), min(100, p + 5)) for p in predictions]

            # Calculate accuracy score
            accuracy_score = self._calculate_model_accuracy(time_series.resource_type)

            return ResourcePrediction(
                resource_type=time_series.resource_type,
                predicted_values=predictions,
                prediction_timestamps=prediction_timestamps,
                confidence_intervals=confidence_intervals,
                model_used=PredictionModel.LSTM,
                accuracy_score=accuracy_score,
                prediction_horizon_minutes=horizon_minutes,
                metadata={
                    'sequence_length': sequence_length,
                    'prediction_steps': prediction_steps,
                    'normalization_mean': mean_val,
                    'normalization_std': std_val
                }
            )

        except Exception as e:
            self._logger.error(f"Error in LSTM prediction: {e}")
            # Fallback to simple prediction
            return await self._predict_with_fallback(time_series, horizon_minutes)

    async def _predict_with_fallback(self, time_series: TimeSeriesData, horizon_minutes: int) -> ResourcePrediction:
        """Generate prediction using fallback methods."""
        values = time_series.values

        if self._config.model_type == PredictionModel.MOVING_AVERAGE:
            # Simple moving average
            window_size = min(10, len(values) // 2)
            if window_size == 0:
                window_size = 1

            recent_avg = np.mean(values[-window_size:])
            predictions = [recent_avg] * (horizon_minutes // (self._config.sampling_interval_seconds // 60))

        elif self._config.model_type == PredictionModel.EXPONENTIAL_SMOOTHING:
            # Exponential smoothing
            alpha = 0.3
            smoothed_value = values[0]
            for value in values[1:]:
                smoothed_value = alpha * value + (1 - alpha) * smoothed_value

            predictions = [smoothed_value] * (horizon_minutes // (self._config.sampling_interval_seconds // 60))

        else:
            # Linear regression fallback
            if len(values) >= 2:
                x = np.arange(len(values))
                coeffs = np.polyfit(x, values, 1)

                future_x = np.arange(len(values), len(values) + horizon_minutes // (self._config.sampling_interval_seconds // 60))
                predictions = np.polyval(coeffs, future_x).tolist()
                predictions = [max(0, min(100, p)) for p in predictions]
            else:
                predictions = [values[-1]] * (horizon_minutes // (self._config.sampling_interval_seconds // 60))

        # Generate timestamps
        start_time = time_series.timestamps[-1]
        prediction_timestamps = [
            start_time + timedelta(minutes=i * (self._config.sampling_interval_seconds // 60))
            for i in range(1, len(predictions) + 1)
        ]

        # Simple confidence intervals
        std_dev = np.std(values[-min(20, len(values)):])
        confidence_intervals = [(max(0, p - std_dev), min(100, p + std_dev)) for p in predictions]

        return ResourcePrediction(
            resource_type=time_series.resource_type,
            predicted_values=predictions,
            prediction_timestamps=prediction_timestamps,
            confidence_intervals=confidence_intervals,
            model_used=self._config.model_type,
            accuracy_score=self._calculate_model_accuracy(time_series.resource_type),
            prediction_horizon_minutes=horizon_minutes,
            metadata={'fallback_method': self._config.model_type.value}
        )

    async def _train_lstm_model(self, resource_type: ResourceType, time_series: TimeSeriesData) -> bool:
        """Train LSTM model for resource prediction."""
        try:
            values = np.array(time_series.values, dtype=np.float32)

            # Normalize data
            mean_val = values.mean()
            std_val = values.std() + 1e-8
            normalized_values = (values - mean_val) / std_val

            # Create training sequences
            sequence_length = min(60, len(values) // 4)
            if sequence_length < 10:
                self._logger.warning(f"Insufficient data for LSTM training: {len(values)} points")
                return False

            X, y = [], []
            for i in range(sequence_length, len(normalized_values)):
                X.append(normalized_values[i-sequence_length:i])
                y.append(normalized_values[i])

            if len(X) < 10:
                self._logger.warning("Insufficient training sequences")
                return False

            X = torch.FloatTensor(X).unsqueeze(-1)
            y = torch.FloatTensor(y)

            # Create model
            model = LSTMPredictor(
                input_size=1,
                hidden_size=self._config.lstm_hidden_size,
                num_layers=self._config.lstm_num_layers,
                output_size=1
            )

            # Training setup
            criterion = nn.MSELoss()
            optimizer = torch.optim.Adam(model.parameters(), lr=self._config.learning_rate)

            # Training loop
            model.train()
            for epoch in range(self._config.epochs):
                optimizer.zero_grad()
                outputs = model(X)
                loss = criterion(outputs.squeeze(), y)
                loss.backward()
                optimizer.step()

                if epoch % 20 == 0:
                    self._logger.debug(f"Epoch {epoch}, Loss: {loss.item():.6f}")

            # Store trained model
            with self._lock:
                self._models[resource_type] = model

            # Calculate and store metrics
            model.eval()
            with torch.no_grad():
                predictions = model(X).squeeze().numpy()
                actual = y.numpy()

                # Denormalize for metrics calculation
                predictions = predictions * std_val + mean_val
                actual = actual * std_val + mean_val

                metrics = self._calculate_prediction_metrics(actual, predictions)
                self._metrics_cache[resource_type] = metrics

            self._logger.info(f"LSTM model trained for {resource_type.value} with MSE: {loss.item():.6f}")
            return True

        except Exception as e:
            self._logger.error(f"Error training LSTM model: {e}")
            return False

    async def _train_fallback_model(self, resource_type: ResourceType, time_series: TimeSeriesData) -> bool:
        """Train fallback prediction model."""
        try:
            # For fallback models, we just store the time series data
            with self._lock:
                self._time_series_data[resource_type] = time_series

            # Calculate simple metrics
            values = time_series.values
            if len(values) >= 10:
                # Use last 10 values for validation
                train_values = values[:-10]
                test_values = values[-10:]

                # Simple moving average prediction
                window_size = min(5, len(train_values) // 2)
                predictions = []
                for i in range(len(test_values)):
                    if i == 0:
                        pred = np.mean(train_values[-window_size:])
                    else:
                        pred = np.mean(test_values[:i])
                    predictions.append(pred)

                metrics = self._calculate_prediction_metrics(test_values, predictions)
                self._metrics_cache[resource_type] = metrics

            return True

        except Exception as e:
            self._logger.error(f"Error training fallback model: {e}")
            return False

    def _calculate_prediction_metrics(self, actual: List[float], predicted: List[float]) -> PredictionMetrics:
        """Calculate prediction accuracy metrics."""
        actual = np.array(actual)
        predicted = np.array(predicted)

        # Mean Absolute Error
        mae = np.mean(np.abs(actual - predicted))

        # Mean Squared Error
        mse = np.mean((actual - predicted) ** 2)

        # Root Mean Squared Error
        rmse = np.sqrt(mse)

        # Mean Absolute Percentage Error
        mape = np.mean(np.abs((actual - predicted) / (actual + 1e-8))) * 100

        # R-squared score
        ss_res = np.sum((actual - predicted) ** 2)
        ss_tot = np.sum((actual - np.mean(actual)) ** 2)
        r2_score = 1 - (ss_res / (ss_tot + 1e-8))

        # Prediction accuracy (1 - normalized RMSE)
        prediction_accuracy = max(0, 1 - (rmse / (np.max(actual) - np.min(actual) + 1e-8)))

        # Model confidence based on consistency
        model_confidence = max(0, 1 - (np.std(actual - predicted) / (np.std(actual) + 1e-8)))

        return PredictionMetrics(
            mae=mae,
            mse=mse,
            rmse=rmse,
            mape=mape,
            r2_score=r2_score,
            prediction_accuracy=prediction_accuracy,
            model_confidence=model_confidence
        )

    def _calculate_model_accuracy(self, resource_type: ResourceType) -> float:
        """Calculate current model accuracy."""
        with self._lock:
            if resource_type in self._metrics_cache:
                return self._metrics_cache[resource_type].prediction_accuracy
            return 0.5  # Default moderate accuracy

    async def _check_retrain_schedule(self) -> None:
        """Check if any models need retraining."""
        current_time = datetime.now(timezone.utc)

        for resource_type in ResourceType:
            with self._lock:
                last_retrain = self._last_retrain.get(resource_type)
                training_in_progress = self._training_in_progress.get(resource_type, False)

            if (not training_in_progress and
                (not last_retrain or
                 (current_time - last_retrain).total_seconds() > self._config.retrain_interval_hours * 3600)):

                # Schedule retraining in background
                asyncio.create_task(self.retrain_model(resource_type))

    def get_configuration(self) -> PredictionConfiguration:
        """Get current prediction configuration."""
        return self._config

    def update_configuration(self, config: PredictionConfiguration) -> None:
        """Update prediction configuration."""
        with self._lock:
            self._config = config
            # Clear cache to force recalculation with new config
            self._prediction_cache.clear()

        self._logger.info("Prediction configuration updated")

    def get_data_summary(self) -> Dict[str, Any]:
        """Get summary of available data for each resource type."""
        summary = {}

        with self._lock:
            for resource_type in ResourceType:
                buffer = self._data_buffers[resource_type]
                if buffer:
                    timestamps, values = zip(*buffer)
                    summary[resource_type.value] = {
                        'data_points': len(buffer),
                        'time_range_hours': (timestamps[-1] - timestamps[0]).total_seconds() / 3600,
                        'latest_value': values[-1],
                        'average_value': np.mean(values),
                        'has_trained_model': resource_type in self._models
                    }
                else:
                    summary[resource_type.value] = {
                        'data_points': 0,
                        'time_range_hours': 0,
                        'latest_value': None,
                        'average_value': None,
                        'has_trained_model': False
                    }

        return summary
