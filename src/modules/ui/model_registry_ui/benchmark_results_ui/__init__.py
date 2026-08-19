"""
MikroDok Benchmark Results UI Package
Provides comprehensive benchmark results display and analysis interface for model performance evaluation.
"""

# Import benchmark results components
try:
    from .benchmark_results_ui import (
        BenchmarkResultsUI,
        BenchmarkResultsConfig,
        BenchmarkResultsData,
        BenchmarkMetric,
        BenchmarkComparison,
        BenchmarkDisplayMode,
        BenchmarkSortOption,
        BenchmarkFilterOption,
        MetricCategory,
        ComparisonMode,
        ExportFormat
    )
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Benchmark results UI components for MikroDok model registry"

# Export main components
__all__ = [
    "BenchmarkResultsUI",
    "BenchmarkResultsConfig", 
    "BenchmarkResultsData",
    "BenchmarkMetric",
    "BenchmarkComparison",
    "BenchmarkDisplayMode",
    "BenchmarkSortOption",
    "BenchmarkFilterOption",
    "MetricCategory",
    "ComparisonMode",
    "ExportFormat"
]
