"""
Bottleneck Detector Module
Identifies performance bottlenecks and suggests optimization strategies based on resource utilization patterns.
"""

from .bottleneck_detector_lg import (
    BottleneckDetector,
    IBottleneckDetector,
    BottleneckType,
    BottleneckSeverity,
    OptimizationRecommendation,
    PerformanceBottleneck,
    ResourceBottleneck,
    SystemBottleneck,
    BottleneckConfiguration,
    OptimizationStrategy
)

__all__ = [
    'BottleneckDetector',
    'IBottleneckDetector',
    'BottleneckType',
    'BottleneckSeverity',
    'OptimizationRecommendation',
    'PerformanceBottleneck',
    'ResourceBottleneck',
    'SystemBottleneck',
    'BottleneckConfiguration',
    'OptimizationStrategy'
]
