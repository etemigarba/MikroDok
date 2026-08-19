"""
MikroDok Model Details UI Package
Provides comprehensive model details display interface with responsive design and theme integration.
"""

# Import model details components
try:
    from .model_details_ui import (
        ModelDetailsUI,
        ModelDetailsMode,
        ModelDetailsConfig,
        ModelDetailsData,
        ModelArchitectureInfo,
        ModelTrainingHistory,
        ModelPerformanceMetrics,
        ModelVersionInfo,
        ModelDeploymentInfo
    )
except ImportError:
    pass

__all__ = [
    'ModelDetailsUI',
    'ModelDetailsMode',
    'ModelDetailsConfig',
    'ModelDetailsData',
    'ModelArchitectureInfo',
    'ModelTrainingHistory',
    'ModelPerformanceMetrics',
    'ModelVersionInfo',
    'ModelDeploymentInfo'
]
