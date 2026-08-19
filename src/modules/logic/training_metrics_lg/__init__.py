"""
MikroDok Training Metrics Package
Provides comprehensive training metrics processing and analysis functionality including loss calculation, metric aggregation, early stopping, and metric export.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        ILossCalculator,
        IMetricAggregator,
        IEarlyStopping,
        IMetricExporter,
        LossType,
        MetricType,
        AggregationStrategy,
        ExportFormat,
        EarlyStoppingCriteria,
        LossConfiguration,
        MetricConfiguration,
        AggregationConfiguration,
        EarlyStoppingConfiguration,
        ExportConfiguration,
        LossResult,
        MetricResult,
        AggregatedMetrics,
        EarlyStoppingResult,
        ExportResult
    )
except ImportError:
    pass

# Import loss calculator components
try:
    from .loss_calculator_lg.loss_calculator_lg import (
        LossCalculator,
        TrainingLossTracker,
        ValidationLossTracker,
        CustomLossFunction
    )
except ImportError:
    pass

# Import metric aggregator components
try:
    from .metric_aggregator_lg.metric_aggregator_lg import (
        MetricAggregator,
        TrainingMetricsCollector,
        MetricStatistics,
        TimeSeriesMetrics
    )
except ImportError:
    pass

# Import early stopping components
try:
    from .early_stopping_lg.early_stopping_lg import (
        EarlyStopping,
        PatienceTracker,
        ImprovementDetector,
        StoppingCriteriaEvaluator
    )
except ImportError:
    pass

# Import metric exporter components
try:
    from .metric_exporter_lg.metric_exporter_lg import (
        MetricExporter,
        JSONExporter,
        CSVExporter,
        TensorBoardExporter
    )
except ImportError:
    pass

__all__ = [
    # Base interfaces and structures
    'ILossCalculator',
    'IMetricAggregator',
    'IEarlyStopping',
    'IMetricExporter',
    'LossType',
    'MetricType',
    'AggregationStrategy',
    'ExportFormat',
    'EarlyStoppingCriteria',
    'LossConfiguration',
    'MetricConfiguration',
    'AggregationConfiguration',
    'EarlyStoppingConfiguration',
    'ExportConfiguration',
    'LossResult',
    'MetricResult',
    'AggregatedMetrics',
    'EarlyStoppingResult',
    'ExportResult',
    
    # Loss Calculator
    'LossCalculator',
    'TrainingLossTracker',
    'ValidationLossTracker',
    'CustomLossFunction',
    
    # Metric Aggregator
    'MetricAggregator',
    'TrainingMetricsCollector',
    'MetricStatistics',
    'TimeSeriesMetrics',
    
    # Early Stopping
    'EarlyStopping',
    'PatienceTracker',
    'ImprovementDetector',
    'StoppingCriteriaEvaluator',
    
    # Metric Exporter
    'MetricExporter',
    'JSONExporter',
    'CSVExporter',
    'TensorBoardExporter'
]
