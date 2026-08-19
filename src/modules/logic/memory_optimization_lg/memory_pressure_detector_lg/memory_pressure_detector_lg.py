"""
Module: memory_pressure_detector_lg
Description: Monitors memory usage patterns and predicts exhaustion using regression analysis on allocation history
Phase: 7
Location: /src/modules/logic/memory_optimization_lg/memory_pressure_detector_lg/
"""

# Standard library imports
import asyncio
import gc
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Callable, Any
import statistics
import math

# Third-party imports
import psutil
import numpy as np

# Lazy imports for sklearn to prevent scipy loading during app startup
_sklearn_linear_model = None
_sklearn_preprocessing = None

def _get_sklearn_linear_model():
    """Lazy import for sklearn.linear_model to prevent scipy loading during startup."""
    global _sklearn_linear_model
    if _sklearn_linear_model is None:
        try:
            from sklearn import linear_model
            _sklearn_linear_model = linear_model
        except ImportError:
            _sklearn_linear_model = False
    return _sklearn_linear_model

def _get_sklearn_preprocessing():
    """Lazy import for sklearn.preprocessing to prevent scipy loading during startup."""
    global _sklearn_preprocessing
    if _sklearn_preprocessing is None:
        try:
            from sklearn import preprocessing
            _sklearn_preprocessing = preprocessing
        except ImportError:
            _sklearn_preprocessing = False
    return _sklearn_preprocessing

# Local imports
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import ValidationEngine
from src.modules.logic.performance_optimizer_lg.memory_pressure_handler_lg import (
    PressureLevel, MemoryTier
)


class PressureTrend(Enum):
    """Memory pressure trend indicators."""
    STABLE = "STABLE"
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    VOLATILE = "VOLATILE"
    CRITICAL_RISE = "CRITICAL_RISE"


class PredictionModel(Enum):
    """Types of prediction models."""
    LINEAR_REGRESSION = "LINEAR_REGRESSION"
    EXPONENTIAL_SMOOTHING = "EXPONENTIAL_SMOOTHING"
    MOVING_AVERAGE = "MOVING_AVERAGE"
    POLYNOMIAL_REGRESSION = "POLYNOMIAL_REGRESSION"


@dataclass
class MemoryMetrics:
    """Memory usage metrics snapshot."""
    timestamp: datetime
    total_memory_bytes: int
    available_memory_bytes: int
    used_memory_bytes: int
    memory_percent: float
    swap_total_bytes: int
    swap_used_bytes: int
    swap_percent: float
    process_memory_bytes: int
    gc_collections: int
    allocation_rate_bytes_per_sec: float
    deallocation_rate_bytes_per_sec: float


@dataclass
class PressureThreshold:
    """Memory pressure threshold configuration."""
    low_threshold_percent: float = 60.0
    moderate_threshold_percent: float = 75.0
    high_threshold_percent: float = 85.0
    critical_threshold_percent: float = 95.0
    prediction_window_minutes: int = 5
    trend_analysis_window_minutes: int = 10


@dataclass
class AllocationHistory:
    """Historical allocation data for analysis."""
    timestamps: List[datetime] = field(default_factory=list)
    memory_usage: List[float] = field(default_factory=list)
    allocation_rates: List[float] = field(default_factory=list)
    pressure_levels: List[PressureLevel] = field(default_factory=list)
    max_history_size: int = 1000


@dataclass
class PressureEvent:
    """Memory pressure event data."""
    timestamp: datetime
    pressure_level: PressureLevel
    trend: PressureTrend
    current_usage_percent: float
    predicted_exhaustion_time: Optional[datetime]
    confidence_score: float
    metrics: MemoryMetrics
    recommendations: List[str] = field(default_factory=list)


class IMemoryPressureDetector(ABC):
    """Interface for memory pressure detection systems."""
    
    @abstractmethod
    async def start_monitoring(self) -> None:
        """Start memory pressure monitoring."""
        pass
    
    @abstractmethod
    async def stop_monitoring(self) -> None:
        """Stop memory pressure monitoring."""
        pass
    
    @abstractmethod
    def get_current_pressure(self) -> PressureLevel:
        """Get current memory pressure level."""
        pass
    
    @abstractmethod
    def predict_exhaustion_time(self) -> Optional[datetime]:
        """Predict when memory will be exhausted."""
        pass
    
    @abstractmethod
    def get_pressure_trend(self) -> PressureTrend:
        """Get current pressure trend."""
        pass
    
    @abstractmethod
    def register_pressure_callback(self, callback: Callable[[PressureEvent], None]) -> None:
        """Register callback for pressure events."""
        pass


class MemoryPressureDetector(IMemoryPressureDetector):
    """
    Monitors memory usage patterns and predicts exhaustion using regression analysis.
    
    This detector uses machine learning techniques to analyze allocation history
    and predict future memory pressure, enabling proactive memory management.
    """
    
    def __init__(self, 
                 thresholds: Optional[PressureThreshold] = None,
                 app_state_manager: Optional[AppStateManager] = None):
        """Initialize the memory pressure detector."""
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("memory_pressure_detector")
        self._validation_engine = ValidationEngine()
        
        # Configuration
        self._thresholds = thresholds or PressureThreshold()
        
        # Monitoring state
        self._monitoring_active = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._lock = threading.RLock()
        
        # Data collection
        self._allocation_history = AllocationHistory()
        self._metrics_history: deque = deque(maxlen=self._thresholds.prediction_window_minutes * 12)  # 5-second intervals
        self._current_metrics: Optional[MemoryMetrics] = None
        
        # Prediction models (initialized lazily)
        self._linear_model = None
        self._scaler = None
        self._model_trained = False
        
        # Event handling
        self._pressure_callbacks: List[Callable[[PressureEvent], None]] = []
        self._last_pressure_level = PressureLevel.LOW
        
        # Performance tracking
        self._prediction_accuracy_history: deque = deque(maxlen=100)
        
        self._logger.info("Memory pressure detector initialized")

    def _initialize_models(self) -> bool:
        """Initialize sklearn models lazily."""
        if self._linear_model is None:
            sklearn_linear_model = _get_sklearn_linear_model()
            sklearn_preprocessing = _get_sklearn_preprocessing()

            if sklearn_linear_model is False or sklearn_preprocessing is False:
                self._logger.warning("sklearn not available, using fallback prediction")
                return False

            self._linear_model = sklearn_linear_model.LinearRegression()
            self._scaler = sklearn_preprocessing.StandardScaler()

        return True

    async def start_monitoring(self) -> None:
        """Start memory pressure monitoring."""
        try:
            with self._lock:
                if self._monitoring_active:
                    self._logger.warning("Memory pressure monitoring already active")
                    return
                
                self._monitoring_active = True
                self._monitoring_task = asyncio.create_task(self._monitoring_loop())
                
            self._logger.info("Memory pressure monitoring started")
            
        except Exception as e:
            self._logger.error(f"Error starting memory pressure monitoring: {e}")
            raise
    
    async def stop_monitoring(self) -> None:
        """Stop memory pressure monitoring."""
        try:
            with self._lock:
                if not self._monitoring_active:
                    return
                
                self._monitoring_active = False
                
                if self._monitoring_task:
                    self._monitoring_task.cancel()
                    try:
                        await self._monitoring_task
                    except asyncio.CancelledError:
                        pass
                    self._monitoring_task = None
                
            self._logger.info("Memory pressure monitoring stopped")
            
        except Exception as e:
            self._logger.error(f"Error stopping memory pressure monitoring: {e}")
    
    def get_current_pressure(self) -> PressureLevel:
        """Get current memory pressure level."""
        try:
            if not self._current_metrics:
                return PressureLevel.LOW
            
            usage_percent = self._current_metrics.memory_percent
            
            if usage_percent >= self._thresholds.critical_threshold_percent:
                return PressureLevel.CRITICAL
            elif usage_percent >= self._thresholds.high_threshold_percent:
                return PressureLevel.HIGH
            elif usage_percent >= self._thresholds.moderate_threshold_percent:
                return PressureLevel.MODERATE
            else:
                return PressureLevel.LOW
                
        except Exception as e:
            self._logger.error(f"Error getting current pressure: {e}")
            return PressureLevel.LOW
    
    def predict_exhaustion_time(self) -> Optional[datetime]:
        """Predict when memory will be exhausted."""
        try:
            if not self._model_trained or len(self._metrics_history) < 10:
                return None
            
            # Prepare data for prediction
            current_time = time.time()
            recent_metrics = list(self._metrics_history)[-20:]  # Last 20 data points
            
            if len(recent_metrics) < 5:
                return None
            
            # Extract features and target
            X = np.array([[i, m.allocation_rate_bytes_per_sec] for i, m in enumerate(recent_metrics)])
            y = np.array([m.memory_percent for m in recent_metrics])
            
            # Scale features
            X_scaled = self._scaler.fit_transform(X)
            
            # Train model on recent data
            self._linear_model.fit(X_scaled, y)
            
            # Predict future usage
            future_steps = 60  # Predict 5 minutes ahead (5-second intervals)
            future_X = np.array([[len(recent_metrics) + i, recent_metrics[-1].allocation_rate_bytes_per_sec] 
                               for i in range(1, future_steps + 1)])
            future_X_scaled = self._scaler.transform(future_X)
            
            predictions = self._linear_model.predict(future_X_scaled)
            
            # Find when usage exceeds critical threshold
            for i, predicted_usage in enumerate(predictions):
                if predicted_usage >= self._thresholds.critical_threshold_percent:
                    exhaustion_time = datetime.now(timezone.utc) + timedelta(seconds=(i + 1) * 5)
                    return exhaustion_time
            
            return None

        except Exception as e:
            self._logger.error(f"Error predicting exhaustion time: {e}")
            return None

    def get_pressure_trend(self) -> PressureTrend:
        """Get current pressure trend."""
        try:
            if len(self._metrics_history) < 5:
                return PressureTrend.STABLE

            # Analyze recent trend
            recent_metrics = list(self._metrics_history)[-10:]
            usage_values = [m.memory_percent for m in recent_metrics]

            # Calculate trend using linear regression
            X = np.array(range(len(usage_values))).reshape(-1, 1)
            y = np.array(usage_values)

            # Use lazy loading for sklearn
            if self._initialize_models():
                trend_model = self._linear_model.__class__()  # Create new instance
                trend_model.fit(X, y)
                slope = trend_model.coef_[0]
            else:
                # Fallback: simple slope calculation
                slope = (usage_values[-1] - usage_values[0]) / len(usage_values) if len(usage_values) > 1 else 0

            # Calculate volatility
            volatility = statistics.stdev(usage_values) if len(usage_values) > 1 else 0

            # Determine trend
            if volatility > 5.0:  # High volatility
                return PressureTrend.VOLATILE
            elif slope > 2.0:  # Rapid increase
                return PressureTrend.CRITICAL_RISE
            elif slope > 0.5:  # Moderate increase
                return PressureTrend.INCREASING
            elif slope < -0.5:  # Decreasing
                return PressureTrend.DECREASING
            else:  # Stable
                return PressureTrend.STABLE

        except Exception as e:
            self._logger.error(f"Error getting pressure trend: {e}")
            return PressureTrend.STABLE

    def register_pressure_callback(self, callback: Callable[[PressureEvent], None]) -> None:
        """Register callback for pressure events."""
        try:
            with self._lock:
                self._pressure_callbacks.append(callback)
            self._logger.debug("Pressure callback registered")

        except Exception as e:
            self._logger.error(f"Error registering pressure callback: {e}")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        try:
            while self._monitoring_active:
                # Collect current metrics
                metrics = await self._collect_memory_metrics()

                if metrics:
                    # Update history
                    self._update_history(metrics)

                    # Analyze pressure
                    pressure_level = self.get_current_pressure()
                    trend = self.get_pressure_trend()

                    # Check for pressure level changes
                    if pressure_level != self._last_pressure_level:
                        await self._handle_pressure_change(pressure_level, trend, metrics)
                        self._last_pressure_level = pressure_level

                    # Train prediction model periodically
                    if len(self._metrics_history) % 20 == 0:
                        self._train_prediction_model()

                # Wait for next collection interval
                await asyncio.sleep(5.0)  # 5-second intervals

        except asyncio.CancelledError:
            self._logger.info("Memory pressure monitoring cancelled")
        except Exception as e:
            self._logger.error(f"Error in monitoring loop: {e}")

    async def _collect_memory_metrics(self) -> Optional[MemoryMetrics]:
        """Collect current memory metrics."""
        try:
            # Get system memory info
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            # Get process memory info
            process = psutil.Process()
            process_memory = process.memory_info().rss

            # Calculate allocation rates
            allocation_rate = 0.0
            deallocation_rate = 0.0

            if self._current_metrics:
                time_diff = (datetime.now(timezone.utc) - self._current_metrics.timestamp).total_seconds()
                if time_diff > 0:
                    memory_diff = memory.used - self._current_metrics.used_memory_bytes
                    allocation_rate = max(0, memory_diff) / time_diff
                    deallocation_rate = max(0, -memory_diff) / time_diff

            # Get garbage collection stats
            gc_collections = sum(gc.get_count())

            metrics = MemoryMetrics(
                timestamp=datetime.now(timezone.utc),
                total_memory_bytes=memory.total,
                available_memory_bytes=memory.available,
                used_memory_bytes=memory.used,
                memory_percent=memory.percent,
                swap_total_bytes=swap.total,
                swap_used_bytes=swap.used,
                swap_percent=swap.percent,
                process_memory_bytes=process_memory,
                gc_collections=gc_collections,
                allocation_rate_bytes_per_sec=allocation_rate,
                deallocation_rate_bytes_per_sec=deallocation_rate
            )

            self._current_metrics = metrics
            return metrics

        except Exception as e:
            self._logger.error(f"Error collecting memory metrics: {e}")
            return None

    def _update_history(self, metrics: MemoryMetrics) -> None:
        """Update allocation history with new metrics."""
        try:
            with self._lock:
                # Add to metrics history
                self._metrics_history.append(metrics)

                # Update allocation history
                self._allocation_history.timestamps.append(metrics.timestamp)
                self._allocation_history.memory_usage.append(metrics.memory_percent)
                self._allocation_history.allocation_rates.append(metrics.allocation_rate_bytes_per_sec)
                self._allocation_history.pressure_levels.append(self.get_current_pressure())

                # Maintain history size limits
                max_size = self._allocation_history.max_history_size
                if len(self._allocation_history.timestamps) > max_size:
                    self._allocation_history.timestamps = self._allocation_history.timestamps[-max_size:]
                    self._allocation_history.memory_usage = self._allocation_history.memory_usage[-max_size:]
                    self._allocation_history.allocation_rates = self._allocation_history.allocation_rates[-max_size:]
                    self._allocation_history.pressure_levels = self._allocation_history.pressure_levels[-max_size:]

        except Exception as e:
            self._logger.error(f"Error updating history: {e}")

    async def _handle_pressure_change(self, pressure_level: PressureLevel,
                                    trend: PressureTrend, metrics: MemoryMetrics) -> None:
        """Handle pressure level changes."""
        try:
            # Predict exhaustion time
            exhaustion_time = self.predict_exhaustion_time()

            # Calculate confidence score
            confidence_score = self._calculate_confidence_score()

            # Generate recommendations
            recommendations = self._generate_recommendations(pressure_level, trend)

            # Create pressure event
            event = PressureEvent(
                timestamp=datetime.now(timezone.utc),
                pressure_level=pressure_level,
                trend=trend,
                current_usage_percent=metrics.memory_percent,
                predicted_exhaustion_time=exhaustion_time,
                confidence_score=confidence_score,
                metrics=metrics,
                recommendations=recommendations
            )

            # Notify callbacks
            for callback in self._pressure_callbacks:
                try:
                    callback(event)
                except Exception as e:
                    self._logger.error(f"Error in pressure callback: {e}")

            self._logger.info(f"Memory pressure changed to {pressure_level.value} (trend: {trend.value})")

        except Exception as e:
            self._logger.error(f"Error handling pressure change: {e}")

    def _train_prediction_model(self) -> None:
        """Train the prediction model with historical data."""
        try:
            if len(self._allocation_history.memory_usage) < 20:
                return

            # Prepare training data
            X = []
            y = []

            for i in range(10, len(self._allocation_history.memory_usage)):
                # Use last 10 data points as features
                features = self._allocation_history.memory_usage[i-10:i]
                features.extend(self._allocation_history.allocation_rates[i-10:i])
                X.append(features)
                y.append(self._allocation_history.memory_usage[i])

            if len(X) < 5:
                return

            X = np.array(X)
            y = np.array(y)

            # Scale features
            X_scaled = self._scaler.fit_transform(X)

            # Train model
            self._linear_model.fit(X_scaled, y)
            self._model_trained = True

            # Evaluate model accuracy
            predictions = self._linear_model.predict(X_scaled)
            accuracy = 1.0 - np.mean(np.abs(predictions - y) / y)
            self._prediction_accuracy_history.append(accuracy)

            self._logger.debug(f"Prediction model trained with accuracy: {accuracy:.3f}")

        except Exception as e:
            self._logger.error(f"Error training prediction model: {e}")

    def _calculate_confidence_score(self) -> float:
        """Calculate confidence score for predictions."""
        try:
            if not self._prediction_accuracy_history:
                return 0.5  # Default confidence

            # Use recent accuracy as confidence
            recent_accuracy = list(self._prediction_accuracy_history)[-10:]
            confidence = statistics.mean(recent_accuracy) if recent_accuracy else 0.5

            # Adjust based on data availability
            data_factor = min(1.0, len(self._metrics_history) / 50.0)
            confidence *= data_factor

            return max(0.0, min(1.0, confidence))

        except Exception as e:
            self._logger.error(f"Error calculating confidence score: {e}")
            return 0.5

    def _generate_recommendations(self, pressure_level: PressureLevel,
                                trend: PressureTrend) -> List[str]:
        """Generate recommendations based on pressure level and trend."""
        recommendations = []

        try:
            if pressure_level == PressureLevel.CRITICAL:
                recommendations.extend([
                    "Immediate action required: Memory usage critical",
                    "Force garbage collection",
                    "Clear all caches",
                    "Offload data to disk storage",
                    "Reduce batch sizes",
                    "Consider emergency cleanup"
                ])
            elif pressure_level == PressureLevel.HIGH:
                recommendations.extend([
                    "High memory pressure detected",
                    "Clear non-essential caches",
                    "Compress data in memory",
                    "Offload to NVMe storage",
                    "Monitor allocation patterns"
                ])
            elif pressure_level == PressureLevel.MODERATE:
                recommendations.extend([
                    "Moderate memory pressure",
                    "Consider cache cleanup",
                    "Monitor allocation trends",
                    "Prepare for potential offloading"
                ])

            if trend == PressureTrend.CRITICAL_RISE:
                recommendations.append("Memory usage rising rapidly - take immediate action")
            elif trend == PressureTrend.VOLATILE:
                recommendations.append("Memory usage is volatile - investigate allocation patterns")

            return recommendations

        except Exception as e:
            self._logger.error(f"Error generating recommendations: {e}")
            return ["Monitor memory usage closely"]
