"""
Swap Controller Module
Manages NVMe-based virtual VRAM implementation with high-speed page swapping (>3.5GB/s).
"""

from .swap_controller_lg import (
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

__all__ = [
    'SwapController',
    'ISwapController',
    'SwapRequest',
    'SwapResult',
    'SwapStatus',
    'SwapConfiguration',
    'SwapMetrics',
    'SwapPolicy',
    'SwapPriority'
]
