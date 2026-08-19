"""
Allocation Strategy Module
Implements core allocation algorithms for Legacy, Hybrid, and Auto IDRAlloc modes.
"""

from .allocation_strategy_lg import (
    AllocationStrategy,
    IAllocationStrategy,
    IDRAllocMode,
    AllocationDecision,
    HardwareProfile,
    AllocationMetrics,
    StrategyConfiguration,
    AllocationResult
)

__all__ = [
    'AllocationStrategy',
    'IAllocationStrategy',
    'IDRAllocMode',
    'AllocationDecision',
    'HardwareProfile',
    'AllocationMetrics',
    'StrategyConfiguration',
    'AllocationResult'
]
