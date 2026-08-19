"""
Page Manager Module
Handles 4KB page-level operations for efficient disk-based memory extension.
"""

from .page_manager_lg import (
    PageManager,
    IPageManager,
    PageInfo,
    PageStatus,
    PageAllocation,
    PageConfiguration,
    PageMetrics,
    PageMapping,
    PagePool
)

__all__ = [
    'PageManager',
    'IPageManager',
    'PageInfo',
    'PageStatus',
    'PageAllocation',
    'PageConfiguration',
    'PageMetrics',
    'PageMapping',
    'PagePool'
]
