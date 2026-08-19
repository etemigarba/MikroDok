"""
Module: time_series_processor_lg
Description: Processes time-series monitoring data with downsampling and rolling window calculations
Phase: 2
Location: /src/modules/logic/monitoring_aggregator_lg/time_series_processor_lg/
"""

# Standard library imports
import asyncio
import logging
import statistics
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from threading import Lock, RLock
from typing import Dict, List, Optional, Any, Tuple, Union, Callable

# Third-party imports
import psutil

# Local imports
from src.modules.logic.resource_predictor_lg import TimeSeriesData


class DownsamplingMethod(Enum):
    """Methods for downsampling time series data."""
    AVERAGE = "average"
    MAXIMUM = "maximum"
    MINIMUM = "minimum"
    MEDIAN = "median"
    FIRST = "first"
    LAST = "last"
    SUM = "sum"
    INTERPOLATION = "interpolation"


class WindowType(Enum):
    """Types of rolling windows."""
    FIXED = "fixed"
    SLIDING = "sliding"
    EXPONENTIAL = "exponential"
    ADAPTIVE = "adaptive"


class TrendDirection(Enum):
    """Direction of trend in time series."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"


@dataclass
class DownsamplingConfiguration:
    """Configuration for time series downsampling."""
    method: DownsamplingMethod = DownsamplingMethod.AVERAGE
    target_points: int = 1000
    time_interval_seconds: Optional[int] = None
    preserve_peaks: bool = True
    preserve_valleys: bool = True
    interpolation_method: str = "linear"


@dataclass
class WindowConfiguration:
    """Configuration for rolling window calculations."""
    window_type: WindowType = WindowType.SLIDING
    window_size: int = 10
    step_size: int = 1
    alpha: float = 0.1  # For exponential windows
    adaptive_threshold: float = 0.05  # For adaptive windows


@dataclass
class TimeSeriesPoint:
    """Single point in a time series."""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessedTimeSeries:
    """Processed time series with statistics."""
    original_data: TimeSeriesData
    processed_points: List[TimeSeriesPoint]
    statistics: Dict[str, float]
    trend_direction: TrendDirection
    compression_ratio: float
    processing_duration_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RollingWindowResult:
    """Result of rolling window calculation."""
    window_values: List[float]
    window_timestamps: List[datetime]
    statistics: Dict[str, float]
    trend_slope: float
    volatility: float


@dataclass
class TimeSeriesStatistics:
    """Comprehensive statistics for time series data."""
    count: int
    mean: float
    median: float
    std_dev: float
    variance: float
    minimum: float
    maximum: float
    range_value: float
    percentile_25: float
    percentile_75: float
    percentile_95: float
    percentile_99: float
    skewness: float
    kurtosis: float
    trend_slope: float
    autocorrelation: float
    seasonality_score: float


class ITimeSeriesProcessor(ABC):
    """Interface for time series processing systems."""
    
    @abstractmethod
    async def downsample_series(
        self, 
        data: TimeSeriesData, 
        config: DownsamplingConfiguration
    ) -> ProcessedTimeSeries:
        """Downsample time series data."""
        pass
    
    @abstractmethod
    async def calculate_rolling_window(
        self, 
        data: TimeSeriesData, 
        config: WindowConfiguration
    ) -> List[RollingWindowResult]:
        """Calculate rolling window statistics."""
        pass
    
    @abstractmethod
    def calculate_statistics(self, data: TimeSeriesData) -> TimeSeriesStatistics:
        """Calculate comprehensive statistics for time series."""
        pass
    
    @abstractmethod
    def detect_anomalies(
        self, 
        data: TimeSeriesData, 
        threshold_std: float = 2.0
    ) -> List[TimeSeriesPoint]:
        """Detect anomalies in time series data."""
        pass
    
    @abstractmethod
    def smooth_series(
        self, 
        data: TimeSeriesData, 
        method: str = "moving_average",
        window_size: int = 5
    ) -> ProcessedTimeSeries:
        """Smooth time series data to reduce noise."""
        pass
    
    @abstractmethod
    def interpolate_missing_values(
        self, 
        data: TimeSeriesData, 
        method: str = "linear"
    ) -> ProcessedTimeSeries:
        """Interpolate missing values in time series."""
        pass


class TimeSeriesProcessor(ITimeSeriesProcessor):
    """Advanced time series processor with downsampling, windowing, and statistical analysis."""
    
    def __init__(self):
        """Initialize the time series processor."""
        self._logger = logging.getLogger(__name__)
        self._lock = RLock()
        
        # Processing statistics
        self._processing_stats = {
            'total_processed': 0,
            'average_processing_time_ms': 0.0,
            'total_compression_ratio': 0.0,
            'errors_count': 0
        }
        
        self._logger.info("TimeSeriesProcessor initialized")
    
    async def downsample_series(
        self, 
        data: TimeSeriesData, 
        config: DownsamplingConfiguration
    ) -> ProcessedTimeSeries:
        """
        Downsample time series data according to configuration.
        
        Args:
            data: Input time series data
            config: Downsampling configuration
            
        Returns:
            Processed time series with downsampled data
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            if len(data.values) <= config.target_points:
                # No downsampling needed
                processed_points = [
                    TimeSeriesPoint(timestamp=ts, value=val)
                    for ts, val in zip(data.timestamps, data.values)
                ]
                
                return ProcessedTimeSeries(
                    original_data=data,
                    processed_points=processed_points,
                    statistics=self._calculate_basic_statistics(data.values),
                    trend_direction=self._detect_trend(data.values),
                    compression_ratio=1.0,
                    processing_duration_ms=0.0
                )
            
            # Perform downsampling
            if config.time_interval_seconds:
                processed_points = await self._downsample_by_time_interval(data, config)
            else:
                processed_points = await self._downsample_by_target_points(data, config)
            
            # Calculate statistics
            processed_values = [p.value for p in processed_points]
            statistics = self._calculate_basic_statistics(processed_values)
            trend_direction = self._detect_trend(processed_values)
            
            # Calculate compression ratio
            compression_ratio = len(processed_points) / len(data.values)
            
            # Calculate processing duration
            end_time = datetime.now(timezone.utc)
            processing_duration = (end_time - start_time).total_seconds() * 1000
            
            # Update processing statistics
            self._update_processing_stats(processing_duration, compression_ratio)
            
            result = ProcessedTimeSeries(
                original_data=data,
                processed_points=processed_points,
                statistics=statistics,
                trend_direction=trend_direction,
                compression_ratio=compression_ratio,
                processing_duration_ms=processing_duration,
                metadata={
                    'downsampling_method': config.method.value,
                    'target_points': config.target_points,
                    'original_points': len(data.values)
                }
            )
            
            self._logger.debug(f"Downsampled {len(data.values)} points to {len(processed_points)} "
                             f"(ratio: {compression_ratio:.3f})")
            
            return result
            
        except Exception as e:
            self._logger.error(f"Error downsampling time series: {e}")
            self._processing_stats['errors_count'] += 1
            raise

    async def calculate_rolling_window(
        self,
        data: TimeSeriesData,
        config: WindowConfiguration
    ) -> List[RollingWindowResult]:
        """
        Calculate rolling window statistics for time series data.

        Args:
            data: Input time series data
            config: Window configuration

        Returns:
            List of rolling window results
        """
        try:
            if len(data.values) < config.window_size:
                raise ValueError(f"Data length {len(data.values)} < window size {config.window_size}")

            results = []

            if config.window_type == WindowType.SLIDING:
                results = await self._calculate_sliding_windows(data, config)
            elif config.window_type == WindowType.FIXED:
                results = await self._calculate_fixed_windows(data, config)
            elif config.window_type == WindowType.EXPONENTIAL:
                results = await self._calculate_exponential_windows(data, config)
            elif config.window_type == WindowType.ADAPTIVE:
                results = await self._calculate_adaptive_windows(data, config)

            self._logger.debug(f"Calculated {len(results)} rolling windows")
            return results

        except Exception as e:
            self._logger.error(f"Error calculating rolling windows: {e}")
            raise

    def calculate_statistics(self, data: TimeSeriesData) -> TimeSeriesStatistics:
        """
        Calculate comprehensive statistics for time series data.

        Args:
            data: Input time series data

        Returns:
            Comprehensive time series statistics
        """
        try:
            values = data.values
            if not values:
                raise ValueError("Cannot calculate statistics for empty data")

            # Basic statistics
            count = len(values)
            mean = statistics.mean(values)
            median = statistics.median(values)
            std_dev = statistics.stdev(values) if count > 1 else 0.0
            variance = statistics.variance(values) if count > 1 else 0.0
            minimum = min(values)
            maximum = max(values)
            range_value = maximum - minimum

            # Percentiles
            sorted_values = sorted(values)
            percentile_25 = self._calculate_percentile(sorted_values, 25)
            percentile_75 = self._calculate_percentile(sorted_values, 75)
            percentile_95 = self._calculate_percentile(sorted_values, 95)
            percentile_99 = self._calculate_percentile(sorted_values, 99)

            # Advanced statistics
            skewness = self._calculate_skewness(values, mean, std_dev)
            kurtosis = self._calculate_kurtosis(values, mean, std_dev)
            trend_slope = self._calculate_trend_slope(values)
            autocorrelation = self._calculate_autocorrelation(values)
            seasonality_score = self._calculate_seasonality_score(values)

            return TimeSeriesStatistics(
                count=count,
                mean=mean,
                median=median,
                std_dev=std_dev,
                variance=variance,
                minimum=minimum,
                maximum=maximum,
                range_value=range_value,
                percentile_25=percentile_25,
                percentile_75=percentile_75,
                percentile_95=percentile_95,
                percentile_99=percentile_99,
                skewness=skewness,
                kurtosis=kurtosis,
                trend_slope=trend_slope,
                autocorrelation=autocorrelation,
                seasonality_score=seasonality_score
            )

        except Exception as e:
            self._logger.error(f"Error calculating statistics: {e}")
            raise

    def detect_anomalies(
        self,
        data: TimeSeriesData,
        threshold_std: float = 2.0
    ) -> List[TimeSeriesPoint]:
        """
        Detect anomalies in time series data using statistical methods.

        Args:
            data: Input time series data
            threshold_std: Standard deviation threshold for anomaly detection

        Returns:
            List of anomalous points
        """
        try:
            if len(data.values) < 3:
                return []

            mean = statistics.mean(data.values)
            std_dev = statistics.stdev(data.values)

            anomalies = []

            for i, (timestamp, value) in enumerate(zip(data.timestamps, data.values)):
                # Z-score based anomaly detection
                z_score = abs(value - mean) / std_dev if std_dev > 0 else 0

                if z_score > threshold_std:
                    anomaly = TimeSeriesPoint(
                        timestamp=timestamp,
                        value=value,
                        metadata={
                            'z_score': z_score,
                            'threshold': threshold_std,
                            'index': i,
                            'anomaly_type': 'statistical_outlier'
                        }
                    )
                    anomalies.append(anomaly)

            self._logger.debug(f"Detected {len(anomalies)} anomalies out of {len(data.values)} points")
            return anomalies

        except Exception as e:
            self._logger.error(f"Error detecting anomalies: {e}")
            return []

    def smooth_series(
        self,
        data: TimeSeriesData,
        method: str = "moving_average",
        window_size: int = 5
    ) -> ProcessedTimeSeries:
        """
        Smooth time series data to reduce noise.

        Args:
            data: Input time series data
            method: Smoothing method ('moving_average', 'exponential', 'savgol')
            window_size: Size of smoothing window

        Returns:
            Smoothed time series
        """
        start_time = datetime.now(timezone.utc)

        try:
            if len(data.values) < window_size:
                # Return original data if insufficient points
                processed_points = [
                    TimeSeriesPoint(timestamp=ts, value=val)
                    for ts, val in zip(data.timestamps, data.values)
                ]
            else:
                if method == "moving_average":
                    smoothed_values = self._moving_average_smooth(data.values, window_size)
                elif method == "exponential":
                    smoothed_values = self._exponential_smooth(data.values, alpha=0.3)
                elif method == "savgol":
                    smoothed_values = self._savgol_smooth(data.values, window_size)
                else:
                    raise ValueError(f"Unknown smoothing method: {method}")

                processed_points = [
                    TimeSeriesPoint(timestamp=ts, value=val)
                    for ts, val in zip(data.timestamps, smoothed_values)
                ]

            # Calculate statistics
            processed_values = [p.value for p in processed_points]
            statistics = self._calculate_basic_statistics(processed_values)
            trend_direction = self._detect_trend(processed_values)

            # Calculate processing duration
            end_time = datetime.now(timezone.utc)
            processing_duration = (end_time - start_time).total_seconds() * 1000

            return ProcessedTimeSeries(
                original_data=data,
                processed_points=processed_points,
                statistics=statistics,
                trend_direction=trend_direction,
                compression_ratio=1.0,  # No compression in smoothing
                processing_duration_ms=processing_duration,
                metadata={
                    'smoothing_method': method,
                    'window_size': window_size
                }
            )

        except Exception as e:
            self._logger.error(f"Error smoothing time series: {e}")
            raise

    def interpolate_missing_values(
        self,
        data: TimeSeriesData,
        method: str = "linear"
    ) -> ProcessedTimeSeries:
        """
        Interpolate missing values in time series data.

        Args:
            data: Input time series data (may contain None values)
            method: Interpolation method ('linear', 'forward_fill', 'backward_fill')

        Returns:
            Time series with interpolated values
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Convert None values to NaN for processing
            values = []
            valid_indices = []

            for i, value in enumerate(data.values):
                if value is not None and not (isinstance(value, float) and value != value):  # Check for NaN
                    values.append(value)
                    valid_indices.append(i)
                else:
                    values.append(None)

            if len(valid_indices) < 2:
                raise ValueError("Need at least 2 valid values for interpolation")

            # Perform interpolation
            if method == "linear":
                interpolated_values = self._linear_interpolate(values, valid_indices)
            elif method == "forward_fill":
                interpolated_values = self._forward_fill(values)
            elif method == "backward_fill":
                interpolated_values = self._backward_fill(values)
            else:
                raise ValueError(f"Unknown interpolation method: {method}")

            processed_points = [
                TimeSeriesPoint(timestamp=ts, value=val)
                for ts, val in zip(data.timestamps, interpolated_values)
            ]

            # Calculate statistics
            statistics = self._calculate_basic_statistics(interpolated_values)
            trend_direction = self._detect_trend(interpolated_values)

            # Calculate processing duration
            end_time = datetime.now(timezone.utc)
            processing_duration = (end_time - start_time).total_seconds() * 1000

            return ProcessedTimeSeries(
                original_data=data,
                processed_points=processed_points,
                statistics=statistics,
                trend_direction=trend_direction,
                compression_ratio=1.0,
                processing_duration_ms=processing_duration,
                metadata={
                    'interpolation_method': method,
                    'missing_values_count': len(data.values) - len(valid_indices)
                }
            )

        except Exception as e:
            self._logger.error(f"Error interpolating missing values: {e}")
            raise

    async def _downsample_by_time_interval(
        self,
        data: TimeSeriesData,
        config: DownsamplingConfiguration
    ) -> List[TimeSeriesPoint]:
        """Downsample data by fixed time intervals."""
        try:
            if not data.timestamps:
                return []

            interval = timedelta(seconds=config.time_interval_seconds)
            start_time = data.timestamps[0]
            end_time = data.timestamps[-1]

            processed_points = []
            current_time = start_time

            while current_time <= end_time:
                next_time = current_time + interval

                # Find values in this time window
                window_values = []
                window_timestamps = []

                for i, timestamp in enumerate(data.timestamps):
                    if current_time <= timestamp < next_time:
                        window_values.append(data.values[i])
                        window_timestamps.append(timestamp)

                if window_values:
                    # Apply downsampling method
                    if config.method == DownsamplingMethod.AVERAGE:
                        value = statistics.mean(window_values)
                    elif config.method == DownsamplingMethod.MAXIMUM:
                        value = max(window_values)
                    elif config.method == DownsamplingMethod.MINIMUM:
                        value = min(window_values)
                    elif config.method == DownsamplingMethod.MEDIAN:
                        value = statistics.median(window_values)
                    elif config.method == DownsamplingMethod.FIRST:
                        value = window_values[0]
                    elif config.method == DownsamplingMethod.LAST:
                        value = window_values[-1]
                    elif config.method == DownsamplingMethod.SUM:
                        value = sum(window_values)
                    else:
                        value = statistics.mean(window_values)  # Default

                    processed_points.append(TimeSeriesPoint(
                        timestamp=current_time + interval / 2,  # Use middle of interval
                        value=value,
                        metadata={
                            'window_size': len(window_values),
                            'interval_start': current_time,
                            'interval_end': next_time
                        }
                    ))

                current_time = next_time

            return processed_points

        except Exception as e:
            self._logger.error(f"Error downsampling by time interval: {e}")
            raise

    async def _downsample_by_target_points(
        self,
        data: TimeSeriesData,
        config: DownsamplingConfiguration
    ) -> List[TimeSeriesPoint]:
        """Downsample data to target number of points."""
        try:
            total_points = len(data.values)
            step_size = total_points / config.target_points

            processed_points = []

            for i in range(config.target_points):
                start_idx = int(i * step_size)
                end_idx = min(int((i + 1) * step_size), total_points)

                if start_idx >= total_points:
                    break

                # Extract window values
                window_values = data.values[start_idx:end_idx]
                window_timestamps = data.timestamps[start_idx:end_idx]

                if not window_values:
                    continue

                # Apply downsampling method
                if config.method == DownsamplingMethod.AVERAGE:
                    value = statistics.mean(window_values)
                elif config.method == DownsamplingMethod.MAXIMUM:
                    value = max(window_values)
                elif config.method == DownsamplingMethod.MINIMUM:
                    value = min(window_values)
                elif config.method == DownsamplingMethod.MEDIAN:
                    value = statistics.median(window_values)
                elif config.method == DownsamplingMethod.FIRST:
                    value = window_values[0]
                elif config.method == DownsamplingMethod.LAST:
                    value = window_values[-1]
                elif config.method == DownsamplingMethod.SUM:
                    value = sum(window_values)
                else:
                    value = statistics.mean(window_values)  # Default

                # Use middle timestamp of window
                timestamp = window_timestamps[len(window_timestamps) // 2]

                processed_points.append(TimeSeriesPoint(
                    timestamp=timestamp,
                    value=value,
                    metadata={
                        'window_size': len(window_values),
                        'start_index': start_idx,
                        'end_index': end_idx
                    }
                ))

            return processed_points

        except Exception as e:
            self._logger.error(f"Error downsampling by target points: {e}")
            raise

    async def _calculate_sliding_windows(
        self,
        data: TimeSeriesData,
        config: WindowConfiguration
    ) -> List[RollingWindowResult]:
        """Calculate sliding window statistics."""
        results = []

        for i in range(0, len(data.values) - config.window_size + 1, config.step_size):
            window_values = data.values[i:i + config.window_size]
            window_timestamps = data.timestamps[i:i + config.window_size]

            statistics = self._calculate_basic_statistics(window_values)
            trend_slope = self._calculate_trend_slope(window_values)
            volatility = statistics.get('std_dev', 0.0)

            results.append(RollingWindowResult(
                window_values=window_values,
                window_timestamps=window_timestamps,
                statistics=statistics,
                trend_slope=trend_slope,
                volatility=volatility
            ))

        return results

    async def _calculate_fixed_windows(
        self,
        data: TimeSeriesData,
        config: WindowConfiguration
    ) -> List[RollingWindowResult]:
        """Calculate fixed window statistics."""
        results = []

        for i in range(0, len(data.values), config.window_size):
            end_idx = min(i + config.window_size, len(data.values))
            window_values = data.values[i:end_idx]
            window_timestamps = data.timestamps[i:end_idx]

            if len(window_values) < config.window_size:
                break  # Skip incomplete windows

            statistics = self._calculate_basic_statistics(window_values)
            trend_slope = self._calculate_trend_slope(window_values)
            volatility = statistics.get('std_dev', 0.0)

            results.append(RollingWindowResult(
                window_values=window_values,
                window_timestamps=window_timestamps,
                statistics=statistics,
                trend_slope=trend_slope,
                volatility=volatility
            ))

        return results

    async def _calculate_exponential_windows(
        self,
        data: TimeSeriesData,
        config: WindowConfiguration
    ) -> List[RollingWindowResult]:
        """Calculate exponential weighted windows."""
        results = []
        alpha = config.alpha

        for i in range(config.window_size - 1, len(data.values)):
            window_values = []
            window_timestamps = []

            # Calculate exponentially weighted values
            for j in range(i - config.window_size + 1, i + 1):
                weight = alpha * ((1 - alpha) ** (i - j))
                weighted_value = data.values[j] * weight
                window_values.append(weighted_value)
                window_timestamps.append(data.timestamps[j])

            statistics = self._calculate_basic_statistics(window_values)
            trend_slope = self._calculate_trend_slope(window_values)
            volatility = statistics.get('std_dev', 0.0)

            results.append(RollingWindowResult(
                window_values=window_values,
                window_timestamps=window_timestamps,
                statistics=statistics,
                trend_slope=trend_slope,
                volatility=volatility
            ))

        return results

    async def _calculate_adaptive_windows(
        self,
        data: TimeSeriesData,
        config: WindowConfiguration
    ) -> List[RollingWindowResult]:
        """Calculate adaptive window statistics based on volatility."""
        results = []
        threshold = config.adaptive_threshold

        i = config.window_size - 1
        while i < len(data.values):
            # Start with minimum window size
            window_size = config.window_size

            # Expand window if volatility is low
            while (i + 1 < len(data.values) and
                   window_size < len(data.values) - i + config.window_size - 1):

                test_values = data.values[i - window_size + 1:i + 1]
                volatility = statistics.stdev(test_values) if len(test_values) > 1 else 0

                if volatility < threshold:
                    window_size += 1
                else:
                    break

            # Extract final window
            start_idx = max(0, i - window_size + 1)
            window_values = data.values[start_idx:i + 1]
            window_timestamps = data.timestamps[start_idx:i + 1]

            statistics_dict = self._calculate_basic_statistics(window_values)
            trend_slope = self._calculate_trend_slope(window_values)
            volatility = statistics_dict.get('std_dev', 0.0)

            results.append(RollingWindowResult(
                window_values=window_values,
                window_timestamps=window_timestamps,
                statistics=statistics_dict,
                trend_slope=trend_slope,
                volatility=volatility
            ))

            i += config.step_size

        return results

    def _calculate_basic_statistics(self, values: List[float]) -> Dict[str, float]:
        """Calculate basic statistics for a list of values."""
        if not values:
            return {}

        try:
            return {
                'count': len(values),
                'mean': statistics.mean(values),
                'median': statistics.median(values),
                'std_dev': statistics.stdev(values) if len(values) > 1 else 0.0,
                'minimum': min(values),
                'maximum': max(values),
                'range': max(values) - min(values)
            }
        except Exception as e:
            self._logger.error(f"Error calculating basic statistics: {e}")
            return {}

    def _detect_trend(self, values: List[float]) -> TrendDirection:
        """Detect trend direction in values."""
        if len(values) < 2:
            return TrendDirection.STABLE

        try:
            slope = self._calculate_trend_slope(values)
            volatility = statistics.stdev(values) if len(values) > 1 else 0
            mean_value = statistics.mean(values)

            # Normalize slope by mean to get relative change
            relative_slope = abs(slope) / mean_value if mean_value != 0 else 0

            # Determine trend based on slope and volatility
            if volatility > mean_value * 0.2:  # High volatility
                return TrendDirection.VOLATILE
            elif relative_slope < 0.01:  # Very small slope
                return TrendDirection.STABLE
            elif slope > 0:
                return TrendDirection.INCREASING
            else:
                return TrendDirection.DECREASING

        except Exception as e:
            self._logger.error(f"Error detecting trend: {e}")
            return TrendDirection.STABLE

    def _calculate_trend_slope(self, values: List[float]) -> float:
        """Calculate trend slope using linear regression."""
        if len(values) < 2:
            return 0.0

        try:
            n = len(values)
            x = list(range(n))

            # Calculate slope using least squares
            sum_x = sum(x)
            sum_y = sum(values)
            sum_xy = sum(x[i] * values[i] for i in range(n))
            sum_x2 = sum(x[i] ** 2 for i in range(n))

            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
            return slope

        except (ZeroDivisionError, ValueError):
            return 0.0

    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = (percentile / 100.0) * (len(sorted_values) - 1)

        if index.is_integer():
            return sorted_values[int(index)]
        else:
            lower_index = int(index)
            upper_index = lower_index + 1
            weight = index - lower_index

            if upper_index < len(sorted_values):
                return sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight
            else:
                return sorted_values[lower_index]

    def _calculate_skewness(self, values: List[float], mean: float, std_dev: float) -> float:
        """Calculate skewness of values."""
        if len(values) < 3 or std_dev == 0:
            return 0.0

        try:
            n = len(values)
            skewness = sum(((x - mean) / std_dev) ** 3 for x in values) / n
            return skewness
        except Exception:
            return 0.0

    def _calculate_kurtosis(self, values: List[float], mean: float, std_dev: float) -> float:
        """Calculate kurtosis of values."""
        if len(values) < 4 or std_dev == 0:
            return 0.0

        try:
            n = len(values)
            kurtosis = sum(((x - mean) / std_dev) ** 4 for x in values) / n - 3
            return kurtosis
        except Exception:
            return 0.0

    def _calculate_autocorrelation(self, values: List[float], lag: int = 1) -> float:
        """Calculate autocorrelation at specified lag."""
        if len(values) <= lag:
            return 0.0

        try:
            n = len(values)
            mean = statistics.mean(values)

            # Calculate autocorrelation
            numerator = sum((values[i] - mean) * (values[i + lag] - mean)
                          for i in range(n - lag))
            denominator = sum((x - mean) ** 2 for x in values)

            return numerator / denominator if denominator != 0 else 0.0

        except Exception:
            return 0.0

    def _calculate_seasonality_score(self, values: List[float]) -> float:
        """Calculate seasonality score using autocorrelation."""
        if len(values) < 12:  # Need at least 12 points for seasonality
            return 0.0

        try:
            # Check for common seasonal patterns
            seasonal_lags = [7, 12, 24, 30]  # Weekly, monthly, etc.
            max_autocorr = 0.0

            for lag in seasonal_lags:
                if lag < len(values):
                    autocorr = abs(self._calculate_autocorrelation(values, lag))
                    max_autocorr = max(max_autocorr, autocorr)

            return max_autocorr

        except Exception:
            return 0.0

    def _moving_average_smooth(self, values: List[float], window_size: int) -> List[float]:
        """Apply moving average smoothing."""
        if window_size >= len(values):
            return values[:]

        smoothed = []
        half_window = window_size // 2

        for i in range(len(values)):
            start = max(0, i - half_window)
            end = min(len(values), i + half_window + 1)
            window_values = values[start:end]
            smoothed.append(statistics.mean(window_values))

        return smoothed

    def _exponential_smooth(self, values: List[float], alpha: float = 0.3) -> List[float]:
        """Apply exponential smoothing."""
        if not values:
            return []

        smoothed = [values[0]]

        for i in range(1, len(values)):
            smoothed_value = alpha * values[i] + (1 - alpha) * smoothed[i - 1]
            smoothed.append(smoothed_value)

        return smoothed

    def _savgol_smooth(self, values: List[float], window_size: int) -> List[float]:
        """Apply Savitzky-Golay smoothing (simplified version)."""
        # Simplified implementation - just use moving average for now
        return self._moving_average_smooth(values, window_size)

    def _linear_interpolate(self, values: List[Optional[float]], valid_indices: List[int]) -> List[float]:
        """Perform linear interpolation for missing values."""
        result = values[:]

        for i in range(len(values)):
            if values[i] is None:
                # Find surrounding valid values
                left_idx = None
                right_idx = None

                for j in range(i - 1, -1, -1):
                    if j in valid_indices:
                        left_idx = j
                        break

                for j in range(i + 1, len(values)):
                    if j in valid_indices:
                        right_idx = j
                        break

                # Interpolate
                if left_idx is not None and right_idx is not None:
                    left_val = values[left_idx]
                    right_val = values[right_idx]
                    weight = (i - left_idx) / (right_idx - left_idx)
                    result[i] = left_val + weight * (right_val - left_val)
                elif left_idx is not None:
                    result[i] = values[left_idx]  # Forward fill
                elif right_idx is not None:
                    result[i] = values[right_idx]  # Backward fill
                else:
                    result[i] = 0.0  # Default value

        return result

    def _forward_fill(self, values: List[Optional[float]]) -> List[float]:
        """Forward fill missing values."""
        result = []
        last_valid = 0.0

        for value in values:
            if value is not None:
                last_valid = value
                result.append(value)
            else:
                result.append(last_valid)

        return result

    def _backward_fill(self, values: List[Optional[float]]) -> List[float]:
        """Backward fill missing values."""
        result = values[:]

        # Find first valid value from the end
        next_valid = 0.0
        for i in range(len(values) - 1, -1, -1):
            if values[i] is not None:
                next_valid = values[i]
                result[i] = values[i]
            else:
                result[i] = next_valid

        return result

    def _update_processing_stats(self, duration_ms: float, compression_ratio: float) -> None:
        """Update processing statistics."""
        with self._lock:
            self._processing_stats['total_processed'] += 1

            # Update average processing time
            total = self._processing_stats['total_processed']
            current_avg = self._processing_stats['average_processing_time_ms']
            self._processing_stats['average_processing_time_ms'] = (
                (current_avg * (total - 1) + duration_ms) / total
            )

            # Update average compression ratio
            current_compression = self._processing_stats['total_compression_ratio']
            self._processing_stats['total_compression_ratio'] = (
                (current_compression * (total - 1) + compression_ratio) / total
            )

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        with self._lock:
            return self._processing_stats.copy()
