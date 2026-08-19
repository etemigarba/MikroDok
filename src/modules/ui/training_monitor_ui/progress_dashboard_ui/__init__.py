"""
MikroDok Training Progress Dashboard UI Package
Provides comprehensive training progress visualization interface with real-time monitoring and control capabilities.
"""

# Import progress dashboard components
try:
    from .progress_dashboard_ui import (
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
