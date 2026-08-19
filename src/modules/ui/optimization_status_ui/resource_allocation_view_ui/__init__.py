"""
Resource Allocation View UI Module
Displays current IDRAlloc resource distribution across GPU, RAM, and NVMe tiers.
Phase: 2
Location: /src/modules/ui/optimization_status_ui/resource_allocation_view_ui/
"""

from .resource_allocation_view_ui import (
    ResourceAllocationViewUI,
    ResourceTier,
    AllocationStatus,
    AllocationPriority,
    ResourceAllocation,
    TierMetrics,
    AllocationViewConfig
)

__all__ = [
    'ResourceAllocationViewUI',
    'ResourceTier',
    'AllocationStatus', 
    'AllocationPriority',
    'ResourceAllocation',
    'TierMetrics',
    'AllocationViewConfig'
]
