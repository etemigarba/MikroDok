"""
MikroDok Database Package
Provides comprehensive database modules for the MikroDok application.
"""

# Import available database components
try:
    from .app_state_db import (
        UserPreferencesDB,
        StateSnapshotsDB
    )
except ImportError:
    pass

try:
    from .resource_monitoring_db import (
        MonitoringMetricsDB,
        PerformanceHistoryDB,
        OptimizationLogDB,
        ThresholdConfigDB,
        ThermalHistoryDB
    )
except ImportError:
    pass

try:
    from .system_config_db import (
        ConfigStorageDB,
        ConfigVersionsDB
    )
except ImportError:
    pass

try:
    from .documents_db import (
        DocumentRepositoryDB,
        DocumentChunksDB,
        ExtractionResultsDB
    )
except ImportError:
    pass

try:
    from .document_collections_db import (
        CollectionManagerDB,
        CollectionMetadataDB
    )
except ImportError:
    pass

try:
    from .document_queue_db import (
        ProcessingQueueDB,
        QueueStatusDB
    )
except ImportError:
    pass

try:
    from .document_quality_db import (
        QualityMetricsDB,
        DeduplicationCacheDB
    )
except ImportError:
    pass

try:
    from .resource_allocation_db import (
        AllocationProfilesDB,
        MemoryMetricsDB,
        AllocationStateDB
    )
except ImportError:
    pass

try:
    from .vector_storage_db import (
        ChromaDBAdapterDB,
        EmbeddingRepositoryDB,
        CollectionManagerDB
    )
except ImportError:
    pass

try:
    from .search_index_db import (
        InvertedIndexDB,
        DocumentFrequencyDB
    )
except ImportError:
    pass

try:
    from .search_cache_db import (
        QueryCacheDB,
        ResultCacheDB
    )
except ImportError:
    pass

try:
    from .rag_metadata_db import (
        ChunkMappingDB,
        RetrievalHistoryDB
    )
except ImportError:
    pass

try:
    from .training_metrics_db import (
        MetricRepositoryDB,
        MetricAggregationDB,
        MetricIndexingDB
    )
except ImportError:
    pass

try:
    from .training_sessions_db import (
        SessionRepositoryDB,
        SessionStateDB,
        SessionHistoryDB
    )
except ImportError:
    pass

try:
    from .checkpoints_db import (
        CheckpointRegistryDB,
        CheckpointVersioningDB,
        CheckpointCleanupDB
    )
except ImportError:
    pass

try:
    from .training_config_db import (
        ConfigRepositoryDB,
        ConfigVersioningDB,
        PresetManagerDB
    )
except ImportError:
    pass

try:
    from .chat_repository_db import (
        ChatSessionDB,
        ChatMessagesDB,
        InferenceMetricsDB
    )
except ImportError:
    pass

try:
    from .optimization_db import (
        IndexManagerDB,
        VacuumSchedulerDB,
        QueryOptimizerDB
    )
except ImportError:
    pass

try:
    from .system_logs_db import (
        LogEntriesDB,
        AuditTrailDB,
        ErrorHistoryDB,
        PerformanceMetricsDB
    )
except ImportError:
    pass

__all__ = [
    # App state database components
    'UserPreferencesDB',
    'StateSnapshotsDB',

    # Resource monitoring database components
    'MonitoringMetricsDB',
    'PerformanceHistoryDB',
    'OptimizationLogDB',
    'ThresholdConfigDB',
    'ThermalHistoryDB',

    # System configuration database components
    'ConfigStorageDB',
    'ConfigVersionsDB',

    # Documents database components
    'DocumentRepositoryDB',
    'DocumentChunksDB',
    'ExtractionResultsDB',

    # Document collections database components
    'CollectionManagerDB',
    'CollectionMetadataDB',

    # Document queue database components
    'ProcessingQueueDB',
    'QueueStatusDB',

    # Document quality database components
    'QualityMetricsDB',
    'DeduplicationCacheDB',

    # Resource allocation database components
    'AllocationProfilesDB',
    'MemoryMetricsDB',
    'AllocationStateDB',

    # Vector storage database components
    'ChromaDBAdapterDB',
    'EmbeddingRepositoryDB',
    'CollectionManagerDB',

    # Search index database components
    'InvertedIndexDB',
    'DocumentFrequencyDB',

    # Search cache database components
    'QueryCacheDB',
    'ResultCacheDB',

    # RAG metadata database components
    'ChunkMappingDB',
    'RetrievalHistoryDB',

    # Training sessions database components
    'SessionRepositoryDB',
    'SessionStateDB',
    'SessionHistoryDB',

    # Training metrics database components
    'MetricRepositoryDB',
    'MetricAggregationDB',
    'MetricIndexingDB',

    # Checkpoint database components
    'CheckpointRegistryDB',
    'CheckpointVersioningDB',
    'CheckpointCleanupDB',

    # Training configuration database components
    'ConfigRepositoryDB',
    'ConfigVersioningDB',
    'PresetManagerDB',

    # Chat repository database components
    'ChatSessionDB',
    'ChatMessagesDB',
    'InferenceMetricsDB',

    # Optimization database components
    'IndexManagerDB',
    'VacuumSchedulerDB',
    'QueryOptimizerDB',

    # System logs database components
    'LogEntriesDB',
    'AuditTrailDB',
    'ErrorHistoryDB',
    'PerformanceMetricsDB'
]
