"""
Time Series Processor Module
Processes time-series monitoring data with downsampling and rolling window calculations.
"""

from .time_series_processor_lg import (
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
