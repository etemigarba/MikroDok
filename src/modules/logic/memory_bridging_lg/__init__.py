"""
MikroDok Memory Bridging Package
Provides intelligent memory bridging functionality for the IDRAlloc system.
"""

# Import bridge controller components
try:
    from .bridge_controller_lg.bridge_controller_lg import (
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
except ImportError:
    pass

# Import predictive preloader components
try:
    from .predictive_preloader_lg.predictive_preloader_lg import (
        PredictivePreloader,
        IPredictivePreloader,
        AccessPattern,
        PreloadRequest,
        PreloadResult,
        ComputationGraph,
        LayerAccessPrediction,
        PreloaderConfiguration,
        PredictionMetrics
    )
except ImportError:
    pass

# Import transfer queue components
try:
    from .transfer_queue_lg.transfer_queue_lg import (
        TransferQueue,
        ITransferQueue,
        QueuedTransfer,
        QueueConfiguration,
        QueueMetrics,
        TransferScheduler,
        BandwidthAllocator,
        QueueStatus
    )
except ImportError:
    pass

__all__ = [
    # Bridge Controller
    'BridgeController',
    'IBridgeController',
    'TransferRequest',
    'TransferResult',
    'TransferStatus',
    'BridgeConfiguration',
    'BridgeMetrics',
    'EvictionPolicy',
    'TransferPriority',
    
    # Predictive Preloader
    'PredictivePreloader',
    'IPredictivePreloader',
    'AccessPattern',
    'PreloadRequest',
    'PreloadResult',
    'ComputationGraph',
    'LayerAccessPrediction',
    'PreloaderConfiguration',
    'PredictionMetrics',
    
    # Transfer Queue
    'TransferQueue',
    'ITransferQueue',
    'QueuedTransfer',
    'QueueConfiguration',
    'QueueMetrics',
    'TransferScheduler',
    'BandwidthAllocator',
    'QueueStatus'
]
