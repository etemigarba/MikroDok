"""
MikroDok Training Repository Database Package
Provides database modules for training session management, metrics storage, and resource allocation tracking.
"""

# Import training repository database components
try:
    from .training_session_db.training_session_db import (
        TrainingSessionDB,
        TrainingSession,
        TrainingStatus,
        ResourceTier
    )
except ImportError:
    pass

try:
    from .training_metrics_db.training_metrics_db import (
        TrainingMetricsDB,
        TrainingMetric,
        MetricAggregation,
        MetricType,
        MetricPriority
    )
except ImportError:
    pass

try:
    from .resource_allocation_db.resource_allocation_db import (
        ResourceAllocationDB,
        ResourceAllocation,
        AllocationEvent,
        AllocationStrategy,
        MemoryTier,
        AllocationStatus
    )
except ImportError:
    pass

__all__ = [
    # Training session components
    'TrainingSessionDB',
    'TrainingSession',
    'TrainingStatus',
    'ResourceTier',
    
    # Training metrics components
    'TrainingMetricsDB',
    'TrainingMetric',
    'MetricAggregation',
    'MetricType',
    'MetricPriority',
    
    # Resource allocation components
    'ResourceAllocationDB',
    'ResourceAllocation',
    'AllocationEvent',
    'AllocationStrategy',
    'MemoryTier',
    'AllocationStatus'
]
