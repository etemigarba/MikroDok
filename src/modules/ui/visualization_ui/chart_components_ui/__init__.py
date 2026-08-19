"""
MikroDok Chart Components UI Package
Provides reusable chart components for metrics, performance graphs, and resource usage visualization.
Phase: 2-4
Location: /src/modules/ui/visualization_ui/chart_components_ui/
"""

# Import chart components
try:
    from .chart_components_ui import (
        ChartComponentsUI,
        ChartType,
        ChartConfig,
        ChartDataPoint,
        ChartSeries,
        ChartTheme,
        LineChart,
        BarChart,
        AreaChart,
        PieChart,
        GaugeChart,
        SparklineChart,
        HeatmapChart,
        ScatterChart
    )
    
    __all__ = [
        'ChartComponentsUI',
        'ChartType',
        'ChartConfig', 
        'ChartDataPoint',
        'ChartSeries',
        'ChartTheme',
        'LineChart',
        'BarChart',
        'AreaChart',
        'PieChart',
        'GaugeChart',
        'SparklineChart',
        'HeatmapChart',
        'ScatterChart'
    ]
    
except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import chart components: {e}")
    
    __all__ = []
