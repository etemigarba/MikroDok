"""
MikroDok Quality Dashboard UI Package
Provides document quality visualization and metrics dashboard components.
"""

# Import quality dashboard components
try:
    from .quality_dashboard_ui import (
        QualityDashboardUI,
        QualityMetric,
        QualityReport,
        QualityIndicator,
        QualityChartType
    )
except ImportError:
    pass

__all__ = [
    'QualityDashboardUI',
    'QualityMetric', 
    'QualityReport',
    'QualityIndicator',
    'QualityChartType'
]
