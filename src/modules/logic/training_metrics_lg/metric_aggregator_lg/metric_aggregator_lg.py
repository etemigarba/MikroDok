"""
Module: metric_aggregator_lg
Description: Aggregates various training metrics for reporting and analysis with statistical processing
Phase: 4
Location: /src/modules/logic/training_metrics_lg/metric_aggregator_lg/
"""

# Standard library imports
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import statistics

# Third-party imports
import numpy as np

# Local imports
from ..base_interfaces import (
    IMetricAggregator, MetricType, AggregationStrategy, 
    MetricResult, AggregatedMetrics, AggregationConfiguration
)
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ErrorClassifier, ErrorSeverity


class MetricStatistics:
    """Statistical analysis for training metrics."""
    
    def __init__(self, window_size: int = 1000):
        """
        Initialize metric statistics.
        
        Args:
            window_size: Size of the rolling window for statistics
        """
        self.window_size = window_size
        self._values = deque(maxlen=window_size)
        self._timestamps = deque(maxlen=window_size)
        self._lock = threading.Lock()
        self._logger = get_logger(__name__)
    
    def add_value(self, value: float, timestamp: Optional[datetime] = None) -> None:
        """Add a value for statistical analysis."""
        if timestamp is None:
            timestamp = datetime.now()
        
        with self._lock:
            self._values.append(value)
            self._timestamps.append(timestamp)
    
    def get_statistics(self) -> Dict[str, float]:
        """Get comprehensive statistics."""
        with self._lock:
            if not self._values:
                return {
                    'mean': 0.0, 'median': 0.0, 'std': 0.0, 'var': 0.0,
                    'min': 0.0, 'max': 0.0, 'range': 0.0, 'count': 0,
                    'skewness': 0.0, 'kurtosis': 0.0, 'trend': 0.0
                }
            
            values = np.array(self._values)
            
            # Basic statistics
            mean_val = float(np.mean(values))
            median_val = float(np.median(values))
            std_val = float(np.std(values))
            var_val = float(np.var(values))
            min_val = float(np.min(values))
            max_val = float(np.max(values))
            range_val = max_val - min_val
            count = len(values)
            
            # Advanced statistics
            skewness = self._calculate_skewness(values)
            kurtosis = self._calculate_kurtosis(values)
            trend = self._calculate_trend(values)
            
            return {
                'mean': mean_val,
                'median': median_val,
                'std': std_val,
                'var': var_val,
                'min': min_val,
                'max': max_val,
                'range': range_val,
                'count': count,
                'skewness': skewness,
                'kurtosis': kurtosis,
                'trend': trend
            }
    
    def get_percentiles(self, percentiles: List[float]) -> Dict[str, float]:
        """Get specified percentiles."""
        with self._lock:
            if not self._values:
                return {f'p{p}': 0.0 for p in percentiles}
            
            values = np.array(self._values)
            return {f'p{p}': float(np.percentile(values, p)) for p in percentiles}
    
    def _calculate_skewness(self, values: np.ndarray) -> float:
        """Calculate skewness of the distribution."""
        if len(values) < 3:
            return 0.0
        
        mean_val = np.mean(values)
        std_val = np.std(values)
        
        if std_val == 0:
            return 0.0
        
        skew = np.mean(((values - mean_val) / std_val) ** 3)
        return float(skew)
    
    def _calculate_kurtosis(self, values: np.ndarray) -> float:
        """Calculate kurtosis of the distribution."""
        if len(values) < 4:
            return 0.0
        
        mean_val = np.mean(values)
        std_val = np.std(values)
        
        if std_val == 0:
            return 0.0
        
        kurt = np.mean(((values - mean_val) / std_val) ** 4) - 3
        return float(kurt)
    
    def _calculate_trend(self, values: np.ndarray) -> float:
        """Calculate trend (slope) of the values."""
        if len(values) < 2:
            return 0.0
        
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]
        return float(slope)


class TimeSeriesMetrics:
    """Time series analysis for training metrics."""
    
    def __init__(self, max_history: int = 10000):
        """
        Initialize time series metrics.
        
        Args:
            max_history: Maximum number of historical points to keep
        """
        self.max_history = max_history
        self._time_series: Dict[str, List[Tuple[datetime, float]]] = defaultdict(list)
        self._lock = threading.Lock()
        self._logger = get_logger(__name__)
    
    def add_point(self, metric_name: str, value: float, timestamp: Optional[datetime] = None) -> None:
        """Add a time series point."""
        if timestamp is None:
            timestamp = datetime.now()
        
        with self._lock:
            series = self._time_series[metric_name]
            series.append((timestamp, value))
            
            # Maintain max history
            if len(series) > self.max_history:
                series.pop(0)
    
    def get_series(self, metric_name: str, duration: Optional[timedelta] = None) -> List[Tuple[datetime, float]]:
        """Get time series data for a metric."""
        with self._lock:
            series = self._time_series.get(metric_name, [])
            
            if duration is None:
                return series.copy()
            
            # Filter by duration
            cutoff_time = datetime.now() - duration
            filtered_series = [(ts, val) for ts, val in series if ts >= cutoff_time]
            return filtered_series
    
    def get_moving_average(
        self,
        metric_name: str,
        window_size: int,
        duration: Optional[timedelta] = None
    ) -> List[Tuple[datetime, float]]:
        """Get moving average of a time series."""
        series = self.get_series(metric_name, duration)
        
        if len(series) < window_size:
            return series
        
        moving_avg = []
        for i in range(window_size - 1, len(series)):
            window_values = [val for _, val in series[i - window_size + 1:i + 1]]
            avg_value = sum(window_values) / len(window_values)
            moving_avg.append((series[i][0], avg_value))
        
        return moving_avg
    
    def detect_anomalies(
        self,
        metric_name: str,
        threshold_std: float = 2.0,
        window_size: int = 100
    ) -> List[Tuple[datetime, float]]:
        """Detect anomalies in time series data."""
        series = self.get_series(metric_name)
        
        if len(series) < window_size:
            return []
        
        anomalies = []
        
        for i in range(window_size, len(series)):
            # Calculate statistics for the window
            window_values = [val for _, val in series[i - window_size:i]]
            mean_val = statistics.mean(window_values)
            std_val = statistics.stdev(window_values) if len(window_values) > 1 else 0
            
            # Check if current value is an anomaly
            current_value = series[i][1]
            if std_val > 0 and abs(current_value - mean_val) > threshold_std * std_val:
                anomalies.append(series[i])
        
        return anomalies


class TrainingMetricsCollector:
    """Collects and organizes training metrics from various sources."""
    
    def __init__(self):
        """Initialize training metrics collector."""
        self._metrics: Dict[MetricType, List[MetricResult]] = defaultdict(list)
        self._lock = threading.Lock()
        self._logger = get_logger(__name__)
        
        # Statistics and time series for each metric type
        self._statistics: Dict[MetricType, MetricStatistics] = {}
        self._time_series: Dict[MetricType, TimeSeriesMetrics] = {}
        
        # Initialize statistics and time series for each metric type
        for metric_type in MetricType:
            self._statistics[metric_type] = MetricStatistics()
            self._time_series[metric_type] = TimeSeriesMetrics()
    
    def add_metric(self, metric: MetricResult) -> None:
        """Add a metric result to the collection."""
        try:
            with self._lock:
                self._metrics[metric.metric_type].append(metric)
                
                # Update statistics and time series
                self._statistics[metric.metric_type].add_value(
                    metric.metric_value, metric.timestamp
                )
                self._time_series[metric.metric_type].add_point(
                    metric.metric_type.value, metric.metric_value, metric.timestamp
                )
            
            self._logger.debug(f"Added metric: {metric.metric_type.value} = {metric.metric_value}")
            
        except Exception as e:
            self._logger.error(f"Error adding metric: {e}")
    
    def get_metrics(
        self,
        metric_type: Optional[MetricType] = None,
        limit: Optional[int] = None
    ) -> List[MetricResult]:
        """Get collected metrics."""
        with self._lock:
            if metric_type is None:
                # Return all metrics
                all_metrics = []
                for metrics_list in self._metrics.values():
                    all_metrics.extend(metrics_list)
                
                # Sort by timestamp
                all_metrics.sort(key=lambda x: x.timestamp)
                
                if limit:
                    all_metrics = all_metrics[-limit:]
                
                return all_metrics
            else:
                metrics = self._metrics[metric_type].copy()
                if limit:
                    metrics = metrics[-limit:]
                return metrics
    
    def get_statistics(self, metric_type: MetricType) -> Dict[str, float]:
        """Get statistics for a specific metric type."""
        return self._statistics[metric_type].get_statistics()
    
    def get_time_series(
        self,
        metric_type: MetricType,
        duration: Optional[timedelta] = None
    ) -> List[Tuple[datetime, float]]:
        """Get time series data for a metric type."""
        return self._time_series[metric_type].get_series(metric_type.value, duration)
    
    def clear_metrics(self, metric_type: Optional[MetricType] = None) -> None:
        """Clear collected metrics."""
        with self._lock:
            if metric_type is None:
                self._metrics.clear()
                # Reinitialize statistics and time series
                for mt in MetricType:
                    self._statistics[mt] = MetricStatistics()
                    self._time_series[mt] = TimeSeriesMetrics()
            else:
                self._metrics[metric_type].clear()
                self._statistics[metric_type] = MetricStatistics()
                self._time_series[metric_type] = TimeSeriesMetrics()
        
        self._logger.info(f"Cleared metrics for {metric_type.value if metric_type else 'all types'}")


class MetricAggregator(IMetricAggregator):
    """Main metric aggregator with comprehensive aggregation strategies."""
    
    def __init__(self):
        """Initialize metric aggregator."""
        self._logger = get_logger(__name__)
        self._error_classifier = ErrorClassifier()
        self._collector = TrainingMetricsCollector()
        self._lock = threading.Lock()
        
        # Performance tracking
        self._aggregation_times = deque(maxlen=1000)
        self._total_aggregations = 0

    def add_metric(self, metric: MetricResult) -> None:
        """Add a metric for aggregation."""
        self._collector.add_metric(metric)

    def aggregate_metrics(self, config: AggregationConfiguration) -> AggregatedMetrics:
        """Aggregate collected metrics using specified strategy."""
        start_time = time.time()

        try:
            # Get metrics for aggregation
            all_metrics = self._collector.get_metrics(limit=config.window_size)

            if not all_metrics:
                return AggregatedMetrics(
                    metrics={},
                    aggregation_strategy=config.strategy,
                    window_size=0,
                    timestamp=datetime.now(),
                    confidence_score=0.0,
                    metadata={'empty_dataset': True}
                )

            # Group metrics by type
            grouped_metrics: Dict[MetricType, List[float]] = defaultdict(list)
            for metric in all_metrics:
                grouped_metrics[metric.metric_type].append(metric.metric_value)

            # Aggregate each metric type
            aggregated = {}
            for metric_type, values in grouped_metrics.items():
                aggregated_value = self._apply_aggregation_strategy(values, config)
                aggregated[metric_type.value] = aggregated_value

            # Calculate confidence score based on sample size
            total_samples = len(all_metrics)
            confidence_score = min(1.0, total_samples / max(config.window_size, 1))

            # Track performance
            aggregation_time = (time.time() - start_time) * 1000
            with self._lock:
                self._aggregation_times.append(aggregation_time)
                self._total_aggregations += 1

            return AggregatedMetrics(
                metrics=aggregated,
                aggregation_strategy=config.strategy,
                window_size=total_samples,
                timestamp=datetime.now(),
                confidence_score=confidence_score,
                metadata={
                    'aggregation_time_ms': aggregation_time,
                    'metric_types_count': len(grouped_metrics),
                    'strategy_params': config.custom_params
                }
            )

        except Exception as e:
            self._logger.error(f"Error aggregating metrics: {e}")
            classification = self._error_classifier.classify_error(e)

            return AggregatedMetrics(
                metrics={},
                aggregation_strategy=config.strategy,
                window_size=0,
                timestamp=datetime.now(),
                confidence_score=0.0,
                metadata={
                    'error': str(e),
                    'error_severity': classification.severity.value
                }
            )

    def get_metric_history(
        self,
        metric_type: MetricType,
        window_size: Optional[int] = None
    ) -> List[MetricResult]:
        """Get metric history for a specific type."""
        return self._collector.get_metrics(metric_type, window_size)

    def _apply_aggregation_strategy(
        self,
        values: List[float],
        config: AggregationConfiguration
    ) -> float:
        """Apply the specified aggregation strategy to values."""
        if not values:
            return 0.0

        try:
            if config.strategy == AggregationStrategy.MEAN:
                return float(np.mean(values))

            elif config.strategy == AggregationStrategy.MEDIAN:
                return float(np.median(values))

            elif config.strategy == AggregationStrategy.MIN:
                return float(np.min(values))

            elif config.strategy == AggregationStrategy.MAX:
                return float(np.max(values))

            elif config.strategy == AggregationStrategy.STD:
                return float(np.std(values))

            elif config.strategy == AggregationStrategy.PERCENTILE:
                percentile = config.percentile
                return float(np.percentile(values, percentile))

            elif config.strategy == AggregationStrategy.WEIGHTED_AVERAGE:
                weights = config.weights
                if weights and len(weights) == len(values):
                    return float(np.average(values, weights=weights))
                else:
                    # Fall back to simple mean if weights are not provided or mismatched
                    return float(np.mean(values))

            elif config.strategy == AggregationStrategy.EXPONENTIAL_MOVING_AVERAGE:
                alpha = config.alpha
                ema = values[0]
                for value in values[1:]:
                    ema = alpha * value + (1 - alpha) * ema
                return float(ema)

            else:
                self._logger.warning(f"Unknown aggregation strategy: {config.strategy}")
                return float(np.mean(values))

        except Exception as e:
            self._logger.error(f"Error applying aggregation strategy {config.strategy}: {e}")
            return float(np.mean(values))  # Fall back to mean

    def get_aggregation_statistics(self) -> Dict[str, Any]:
        """Get statistics about aggregation performance."""
        with self._lock:
            if not self._aggregation_times:
                return {
                    'avg_aggregation_time_ms': 0.0,
                    'min_aggregation_time_ms': 0.0,
                    'max_aggregation_time_ms': 0.0,
                    'total_aggregations': 0,
                    'metrics_collected': 0
                }

            times = np.array(self._aggregation_times)
            total_metrics = sum(len(self._collector.get_metrics(mt)) for mt in MetricType)

            return {
                'avg_aggregation_time_ms': float(np.mean(times)),
                'min_aggregation_time_ms': float(np.min(times)),
                'max_aggregation_time_ms': float(np.max(times)),
                'total_aggregations': self._total_aggregations,
                'metrics_collected': total_metrics
            }

    def get_metric_statistics(self, metric_type: MetricType) -> Dict[str, float]:
        """Get comprehensive statistics for a specific metric type."""
        return self._collector.get_statistics(metric_type)

    def get_time_series_data(
        self,
        metric_type: MetricType,
        duration: Optional[timedelta] = None
    ) -> List[Tuple[datetime, float]]:
        """Get time series data for a metric type."""
        return self._collector.get_time_series(metric_type, duration)

    def detect_metric_anomalies(
        self,
        metric_type: MetricType,
        threshold_std: float = 2.0,
        window_size: int = 100
    ) -> List[Tuple[datetime, float]]:
        """Detect anomalies in metric time series."""
        time_series = self._collector._time_series[metric_type]
        return time_series.detect_anomalies(
            metric_type.value, threshold_std, window_size
        )

    def clear_metrics(self, metric_type: Optional[MetricType] = None) -> None:
        """Clear collected metrics."""
        self._collector.clear_metrics(metric_type)

    def export_metrics_summary(self) -> Dict[str, Any]:
        """Export a comprehensive summary of all metrics."""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'metric_types': {},
            'aggregation_performance': self.get_aggregation_statistics()
        }

        for metric_type in MetricType:
            metrics = self._collector.get_metrics(metric_type)
            if metrics:
                stats = self.get_metric_statistics(metric_type)
                time_series = self.get_time_series_data(metric_type, timedelta(hours=24))
                anomalies = self.detect_metric_anomalies(metric_type)

                summary['metric_types'][metric_type.value] = {
                    'count': len(metrics),
                    'latest_value': metrics[-1].metric_value if metrics else 0.0,
                    'statistics': stats,
                    'time_series_points': len(time_series),
                    'anomalies_detected': len(anomalies),
                    'last_updated': metrics[-1].timestamp.isoformat() if metrics else None
                }

        return summary
