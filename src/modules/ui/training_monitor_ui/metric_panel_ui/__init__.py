"""
MikroDok Metric Panel UI Package
Provides comprehensive training metrics display and analysis interface components.
"""

# Import metric panel components
try:
    from .metric_panel_ui import (
        MetricPanelUI,
        MetricDisplayMode,
        MetricCategory,
        MetricCard,
        MetricConfiguration,
        TrainingMetricData
    )
    
    __all__ = [
        'MetricPanelUI',
        'MetricDisplayMode',
        'MetricCategory',
        'MetricCard',
        'MetricConfiguration',
        'TrainingMetricData'
    ]
    
except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import metric panel components: {e}")
    
    __all__ = []
