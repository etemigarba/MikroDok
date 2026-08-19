"""
MikroDok Visualization UI Package
Provides reusable chart components, metric cards, progress indicators, and status badges.
Phase: 2-4
Location: /src/modules/ui/visualization_ui/
"""

# Import visualization components
try:
    from .chart_components_ui.chart_components_ui import (
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

    from .metric_cards_ui.metric_cards_ui import (
        MetricCardsUI,
        MetricCard,
        MetricCategory,
        MetricCardVariant,
        TrendDirection,
        MetricTrend,
        MetricCardsConfiguration,
        MetricCardsState
    )

    from .progress_indicators_ui.progress_indicators_ui import (
        ProgressIndicatorsUI,
        LinearProgressBar,
        CircularProgressRing,
        SteppedProgressIndicator,
        IndeterminateProgress,
        ProgressType,
        ProgressState,
        ProgressSize,
        ProgressConfig,
        ProgressMetrics,
        create_linear_progress,
        create_circular_progress,
        create_stepped_progress,
        create_indeterminate_progress
    )

    from .status_badges_ui.status_badges_ui import (
        StatusBadgesUI,
        StatusBadge,
        StatusType,
        StatusState,
        StatusSize,
        StatusVariant,
        BadgeConfig,
        BadgeMetrics,
        NotificationBadge,
        CountBadge,
        HealthBadge,
        ProcessingBadge,
        TrainingBadge,
        SystemBadge,
        CustomBadge,
        BadgeGroup,
        BadgeContainer,
        create_training_status_badge,
        create_health_indicator_badge,
        create_notification_counter,
        create_processing_indicator,
        create_system_status_badge
    )

    __all__ = [
        # Chart Components
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
        'ScatterChart',
        # Metric Cards
        'MetricCardsUI',
        'MetricCard',
        'MetricCategory',
        'MetricCardVariant',
        'TrendDirection',
        'MetricTrend',
        'MetricCardsConfiguration',
        'MetricCardsState',
        # Progress Indicators
        'ProgressIndicatorsUI',
        'LinearProgressBar',
        'CircularProgressRing',
        'SteppedProgressIndicator',
        'IndeterminateProgress',
        'ProgressType',
        'ProgressState',
        'ProgressSize',
        'ProgressConfig',
        'ProgressMetrics',
        'create_linear_progress',
        'create_circular_progress',
        'create_stepped_progress',
        'create_indeterminate_progress',
        # Status Badges
        'StatusBadgesUI',
        'StatusBadge',
        'StatusType',
        'StatusState',
        'StatusSize',
        'StatusVariant',
        'BadgeConfig',
        'BadgeMetrics',
        'NotificationBadge',
        'CountBadge',
        'HealthBadge',
        'ProcessingBadge',
        'TrainingBadge',
        'SystemBadge',
        'CustomBadge',
        'BadgeGroup',
        'BadgeContainer',
        'create_training_status_badge',
        'create_health_indicator_badge',
        'create_notification_counter',
        'create_processing_indicator',
        'create_system_status_badge'
    ]
    
except ImportError as e:
    # Handle import errors gracefully during development
    import warnings
    warnings.warn(f"Could not import chart components: {e}")
    
    __all__ = []
