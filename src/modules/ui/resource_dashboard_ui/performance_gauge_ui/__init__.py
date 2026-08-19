"""
Performance Gauge UI Package
Provides comprehensive performance gauge visualization components.
"""

try:
    from .performance_gauge_ui import (
        PerformanceGaugeUI,
        GaugeConfiguration,
        GaugeType,
        GaugeStyle,
        PerformanceMetrics,
        GaugeThreshold
    )
    
    __all__ = [
        'PerformanceGaugeUI',
        'GaugeConfiguration', 
        'GaugeType',
        'GaugeStyle',
        'PerformanceMetrics',
        'GaugeThreshold'
    ]
    
except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import performance gauge components: {e}")
    
    __all__ = []
