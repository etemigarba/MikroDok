"""
MikroDok Loss Chart UI Package
Provides real-time loss curve visualization with interactive charts for training monitoring.
Phase: 4
Location: /src/modules/ui/training_monitor_ui/loss_chart_ui/
"""

# Import loss chart components
try:
    from .loss_chart_ui import (
        LossChartUI,
        LossDataPoint,
        LossChartConfig,
        ChartViewMode,
        LossType,
        ChartTimeRange,
        LossChartData
    )
    
    __all__ = [
        'LossChartUI',
        'LossDataPoint',
        'LossChartConfig', 
        'ChartViewMode',
        'LossType',
        'ChartTimeRange',
        'LossChartData'
    ]
    
except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import loss chart components: {e}")
    
    __all__ = []
