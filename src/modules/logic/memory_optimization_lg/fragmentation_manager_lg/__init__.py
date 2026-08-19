"""
Fragmentation Manager Module
Handles memory fragmentation issues with pool pre-allocation and defragmentation strategies.
"""

from .fragmentation_manager_lg import (
    FragmentationManager,
    IFragmentationManager,
    FragmentationLevel,
    DefragmentationStrategy,
    MemoryPool,
    FragmentationMetrics,
    DefragmentationResult,
    PoolConfiguration,
    FragmentationEvent
)

__all__ = [
    'FragmentationManager',
    'IFragmentationManager',
    'FragmentationLevel',
    'DefragmentationStrategy',
    'MemoryPool',
    'FragmentationMetrics',
    'DefragmentationResult',
    'PoolConfiguration',
    'FragmentationEvent'
]
