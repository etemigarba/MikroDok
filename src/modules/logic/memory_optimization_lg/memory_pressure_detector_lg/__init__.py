"""
Memory Pressure Detector Module
Monitors memory usage patterns and predicts exhaustion using regression analysis on allocation history.
"""

from .memory_pressure_detector_lg import (
    MemoryPressureDetector,
    IMemoryPressureDetector,
    PressureLevel,
    PressureTrend,
    MemoryMetrics,
    PressureThreshold,
    PredictionModel,
    AllocationHistory,
    PressureEvent
)

__all__ = [
    'MemoryPressureDetector',
    'IMemoryPressureDetector',
    'PressureLevel',
    'PressureTrend',
    'MemoryMetrics',
    'PressureThreshold',
    'PredictionModel',
    'AllocationHistory',
    'PressureEvent'
]
