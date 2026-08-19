"""
MikroDok Metric Cards UI Package
Provides reusable metric display cards with real-time updates, trend indicators, and responsive design.
Phase: 2-4
Location: /src/modules/ui/visualization_ui/metric_cards_ui/
"""

# Import metric cards components
try:
    from .metric_cards_ui import (
        MetricCardsUI,
        MetricCard,
        MetricCategory,
        MetricCardVariant,
        TrendDirection,
        MetricTrend,
        MetricCardsConfiguration,
        MetricCardsState
    )
    
    __all__ = [
        'MetricCardsUI',
        'MetricCard',
        'MetricCategory',
        'MetricCardVariant',
        'TrendDirection',
        'MetricTrend',
        'MetricCardsConfiguration',
        'MetricCardsState'
    ]
    
except ImportError as e:
    print(f"Warning: Could not import metric cards components: {e}")
    __all__ = []

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Metric display cards with real-time updates and responsive design"
