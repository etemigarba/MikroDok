"""
Bridge Controller Module
Orchestrates data movement between memory tiers using DMA transfers with LRU eviction policies.
"""

from .bridge_controller_lg import (
    BridgeController,
    IBridgeController,
    TransferRequest,
    TransferResult,
    TransferStatus,
    BridgeConfiguration,
    BridgeMetrics,
    EvictionPolicy,
    TransferPriority
)

__all__ = [
    'BridgeController',
    'IBridgeController',
    'TransferRequest',
    'TransferResult',
    'TransferStatus',
    'BridgeConfiguration',
    'BridgeMetrics',
    'EvictionPolicy',
    'TransferPriority'
]
