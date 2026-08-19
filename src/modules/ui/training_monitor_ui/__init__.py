"""
MikroDok Training Monitor UI Package
Provides comprehensive training monitoring interface components including progress dashboard, loss charts, metric panels, and control interfaces.
"""

# Import training monitor components
try:
    from .progress_dashboard_ui.progress_dashboard_ui import (
        ProgressDashboardUI,
        DashboardView,
        ProgressStatus,
        ProgressConfiguration,
        TrainingProgressData
    )

    __all__ = [
        'ProgressDashboardUI',
        'DashboardView',
        'ProgressStatus',
        'ProgressConfiguration',
        'TrainingProgressData'
    ]

except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import progress dashboard components: {e}")

    __all__ = []

# Import metric panel components
try:
    from .metric_panel_ui.metric_panel_ui import (
        MetricPanelUI,
        MetricDisplayMode,
        MetricCategory,
        MetricCard,
        MetricConfiguration,
        TrainingMetricData
    )

    __all__.extend([
        'MetricPanelUI',
        'MetricDisplayMode',
        'MetricCategory',
        'MetricCard',
        'MetricConfiguration',
        'TrainingMetricData'
    ])

except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import metric panel components: {e}")

# Import control panel components
try:
    from .control_panel_ui.control_panel_ui import (
        ControlPanelUI,
        TrainingControlState,
        ControlPanelConfiguration,
        TrainingControlAction,
        SessionControlAction
    )

    __all__.extend([
        'ControlPanelUI',
        'TrainingControlState',
        'ControlPanelConfiguration',
        'TrainingControlAction',
        'SessionControlAction'
    ])

except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import control panel components: {e}")

# Import loss chart components
try:
    from .loss_chart_ui.loss_chart_ui import (
        LossChartUI,
        LossDataPoint,
        LossChartConfig,
        ChartViewMode,
        LossType,
        ChartTimeRange,
        LossChartData
    )

    __all__.extend([
        'LossChartUI',
        'LossDataPoint',
        'LossChartConfig',
        'ChartViewMode',
        'LossType',
        'ChartTimeRange',
        'LossChartData'
    ])

except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import loss chart components: {e}")
