"""
MikroDok NVMe Virtual Memory Package
Provides NVMe-based virtual memory functionality for the IDRAlloc system.
"""

# Import swap controller components
try:
    from .swap_controller_lg.swap_controller_lg import (
        SwapController,
        ISwapController,
        SwapRequest,
        SwapResult,
        SwapStatus,
        SwapConfiguration,
        SwapMetrics,
        SwapPolicy,
        SwapPriority
    )
except ImportError:
    pass

# Import page manager components
try:
    from .page_manager_lg.page_manager_lg import (
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
except ImportError:
    pass

__all__ = [
    # Swap Controller
    'SwapController',
    'ISwapController',
    'SwapRequest',
    'SwapResult',
    'SwapStatus',
    'SwapConfiguration',
    'SwapMetrics',
    'SwapPolicy',
    'SwapPriority',
    
    # Page Manager
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
