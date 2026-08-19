"""
MikroDok Monitoring Aggregator Package
Provides comprehensive metrics aggregation and time series processing functionality for unified monitoring.
"""

# Import metrics aggregator components
from .metrics_aggregator_lg.metrics_aggregator_lg import (
    MetricsAggregator,
    IMetricsAggregator,
    AggregationStrategy,
    MetricType,
    AggregationPeriod,
    AggregationRule,
    AggregatedMetric,
    MetricsSnapshot,
    AggregationConfiguration
)

# Import time series processor components
from .time_series_processor_lg.time_series_processor_lg import (
    TimeSeriesProcessor,
    ITimeSeriesProcessor,
    DownsamplingMethod,
    WindowType,
    TrendDirection,
    DownsamplingConfiguration,
    WindowConfiguration,
    TimeSeriesPoint,
    ProcessedTimeSeries,
    RollingWindowResult,
    TimeSeriesStatistics
)

__all__ = [
    # Metrics Aggregator
    'MetricsAggregator',
    'IMetricsAggregator',
    'AggregationStrategy',
    'MetricType',
    'AggregationPeriod',
    'AggregationRule',
    'AggregatedMetric',
    'MetricsSnapshot',
    'AggregationConfiguration',
    
    # Time Series Processor
    'TimeSeriesProcessor',
    'ITimeSeriesProcessor',
    'DownsamplingMethod',
    'WindowType',
    'TrendDirection',
    'DownsamplingConfiguration',
    'WindowConfiguration',
    'TimeSeriesPoint',
    'ProcessedTimeSeries',
    'RollingWindowResult',
    'TimeSeriesStatistics'
]
