"""
MikroDok Logic Layer Package
Provides comprehensive business logic functionality for the MikroDok application.
"""

# Import available logic components
try:
    from .error_handling_lg import (
        ErrorClassifier,
        ErrorSeverity,
        ErrorCategory,
        ErrorContext,
        RecoveryAction,
        UserNotification,
        ClassificationResult,
        RecoveryOrchestrator,
        RecoveryStrategy,
        RecoveryResult,
        RecoveryWorkflow,
        CrashHandler,
        CrashType,
        CrashContext,
        RecoveryPoint,
        ValidationEngine,
        ValidationRule,
        ValidationResult,
        ValidationError
    )
except ImportError:
    pass

try:
    from .logging_infrastructure_lg import (
        LogManager,
        LogLevel,
        LogDestination,
        LogEntry,
        LoggerConfig,
        LogFormatter,
        MemoryLogHandler,
        get_log_manager,
        get_logger,
        log_performance,
        performance_timer
    )
except ImportError:
    pass

# Import resource monitoring modules
try:
    from .resource_monitor_lg import (
        HardwareMonitor,
        GPUMonitor,
        MemoryMonitor,
        DiskMonitor,
        ThermalMonitor,
        IResourceMonitor,
        ResourceMetrics,
        MonitoringConfiguration,
        MonitoringThresholds,
        ResourceAlert,
        AlertSeverity,
        GPUMetrics,
        GPUInfo,
        CUDAInfo,
        ROCmInfo,
        MemoryMetrics,
        MemoryAllocationPattern,
        SwapUsageInfo,
        DiskMetrics,
        IOPerformanceMetrics,
        StorageInfo,
        ThermalMetrics,
        TemperatureThresholds,
        ThrottlingInfo
    )
except ImportError:
    pass

try:
    from .state_management_lg import (
        AppStateManager,
        ApplicationState,
        StateTransition,
        StateValidator,
        StateManagerConfiguration,
        StateManagerMetrics,
        StateManagerResult,
        StatePersistenceManager,
        PersistenceMode,
        SerializationFormat,
        PersistenceConfiguration,
        StateSnapshot,
        PersistenceMetrics,
        StatePersistenceResult
    )
except ImportError:
    pass

try:
    from .system_initialization_lg import (
        StartupOrchestrator,
        InitializationPhase,
        StartupResult,
        ComponentStatus,
        StartupContext,
        PreflightChecker,
        SystemRequirement,
        ValidationReport,
        RequirementStatus,
        HardwareCapability,
        ShutdownCoordinator,
        ShutdownPhase,
        ShutdownResult,
        CleanupStatus,
        ShutdownContext,
        DependencyResolver
    )
except ImportError:
    pass

try:
    from .system_requirements_lg import (
        HardwareValidator,
        IHardwareValidator,
        HardwareRequirement,
        HardwareCapability,
        HardwareValidationResult,
        SystemArchitecture,
        GPUInfo,
        CPUInfo,
        MemoryInfo,
        StorageInfo,
        DependencyChecker,
        IDependencyChecker,
        DependencyRequirement,
        DependencyType,
        DependencyStatus,
        DependencyValidationResult,
        PackageInfo,
        LibraryInfo,
        DriverInfo
    )
except ImportError:
    pass

# Import embedding generation modules
try:
    from .embedding_generation_lg import (
        DocumentEmbedder,
        BatchProcessor,
        EmbeddingCache,
        IDocumentEmbedder,
        IBatchProcessor,
        IEmbeddingCache,
        EmbeddingResult,
        EmbeddingMetadata,
        BatchProcessingResult,
        CacheResult,
        EmbeddingConfig,
        BatchConfig,
        CacheConfig,
        EmbeddingStatus,
        BatchStatus,
        CacheStatus,
        EmbeddingModel,
        VectorDimensions
    )
except ImportError:
    pass

# Import hybrid search modules
try:
    from .hybrid_search_lg import (
        SemanticSearcher,
        KeywordSearcher,
        ResultFusion,
        ISemanticSearcher,
        IKeywordSearcher,
        IResultFusion,
        SearchResultItem,
        SemanticSearchResult,
        KeywordSearchResult,
        HybridSearchResult,
        SemanticSearchConfig,
        KeywordSearchConfig,
        FusionConfig,
        HybridSearchConfig,
        SearchType,
        FusionStrategy,
        SearchStatus,
        RankingMethod,
        VectorEmbedder,
        SimilarityMatcher,
        SemanticRanker,
        BM25Calculator,
        InvertedIndexBuilder,
        TermProcessor,
        ScoreNormalizer,
        RankFuser,
        DiversityOptimizer
    )
except ImportError:
    pass

# Import query processor modules
try:
    from .query_processor_lg import (
        QueryParser,
        QueryExpander,
        QueryOptimizer,
        IQueryParser,
        IQueryExpander,
        IQueryOptimizer,
        QueryType,
        QueryOperator,
        FieldType,
        ExpansionMethod,
        OptimizationStrategy,
        QueryStatus,
        QueryFilter,
        QueryTerm,
        ParsedQuery,
        ExpandedTerm,
        QueryExpansionResult,
        ExecutionPlan,
        IndexStatistics,
        QueryOptimizationResult,
        QueryParsingConfig,
        QueryExpansionConfig,
        QueryOptimizationConfig,
        BooleanQueryParser,
        PhraseQueryParser,
        FieldQueryParser,
        FilterParser,
        OperatorParser,
        SynonymExpander,
        SemanticExpander,
        StemExpander,
        ContextualExpander,
        DomainExpander,
        CostEstimator,
        ExecutionPlanner,
        IndexAnalyzer,
        StatisticsCollector,
        QueryRewriter
    )
except ImportError:
    pass

# Import performance optimizer modules
try:
    from .performance_optimizer_lg import (
        OptimizationTrigger,
        IOptimizationTrigger,
        TriggerCondition,
        TriggerType,
        OptimizationAction,
        TriggerConfiguration,
        MetricThreshold,
        TriggerEvent,
        OptimizationContext,
        MemoryPressureHandler,
        IMemoryPressureHandler,
        PressureLevel,
        MemoryAction,
        AllocationStrategy,
        CleanupStrategy,
        MemoryTier,
        PressureConfiguration,
        MemoryPressureEvent,
        BatchSizeOptimizer,
        IBatchSizeOptimizer,
        BatchOptimizationStrategy,
        ResourceConstraints,
        BatchConfiguration,
        OptimizationMetrics,
        BatchSizeRecommendation,
        PerformanceProfile,
        CacheOptimizer,
        ICacheOptimizer,
        EvictionPolicy,
        PrefetchStrategy,
        CacheConfiguration,
        AccessPattern,
        CacheMetrics,
        CacheOptimizationResult,
        CacheLevel
    )
except ImportError:
    pass

# Import performance optimization modules
try:
    from .performance_optimization_lg import (
        ResourceOptimizer,
        IResourceOptimizer,
        OptimizationStrategy,
        ResourceTier,
        AllocationPriority,
        ResourceAllocation,
        OptimizationTarget,
        OptimizationResult,
        ThrottleController,
        IThrottleController,
        ThrottleLevel,
        ThrottleReason,
        ThrottleTarget,
        ThrottleConfiguration,
        ThrottleState,
        ThrottleEvent,
        MemoryPoolAllocator,
        MemoryPool,
        IMemoryPoolAllocator,
        PoolType,
        PoolStatus,
        PoolConfiguration,
        MemoryBlock,
        PoolStatistics,
        AllocationRequest,
        BatchProcessor,
        IBatchProcessor,
        BatchType,
        ProcessingMode,
        BatchPriority,
        BatchStatus,
        BatchItem,
        BatchJob,
        ProcessingConfiguration,
        ProcessingMetrics
    )
except ImportError:
    pass

# Import memory allocation modules
try:
    from .memory_allocation_lg import (
        AllocationStrategy,
        IAllocationStrategy,
        IDRAllocMode,
        AllocationDecision,
        HardwareProfile,
        AllocationMetrics,
        StrategyConfiguration,
        AllocationResult,
        MemoryTierManager,
        IMemoryTierManager,
        MemoryTierInfo,
        TierCapacity,
        TierBandwidth,
        TierStatus,
        TierConfiguration,
        TierMetrics,
        LayerDistributor,
        ILayerDistributor,
        LayerAllocationMap,
        LayerInfo,
        AccessPattern,
        LayerPriority,
        DistributionStrategy,
        DistributionResult
    )
except ImportError:
    pass

# Import memory optimization modules
try:
    from .memory_optimization_lg import (
        MemoryPressureDetector,
        IMemoryPressureDetector,
        PressureLevel,
        PressureTrend,
        MemoryMetrics,
        PressureThreshold,
        PredictionModel,
        AllocationHistory,
        PressureEvent,
        AdaptiveReallocator,
        IAdaptiveReallocator,
        ReallocationStrategy,
        PerformanceMetrics,
        ResourceAvailability,
        ReallocationDecision,
        AdaptationTrigger,
        ReallocationResult,
        OptimizationTarget,
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
except ImportError:
    pass

# Import NVMe virtual memory modules
try:
    from .nvme_virtual_memory_lg import (
        SwapController,
        ISwapController,
        SwapRequest,
        SwapResult,
        SwapStatus,
        SwapConfiguration,
        SwapMetrics,
        SwapPolicy,
        SwapPriority,
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

# Import monitoring aggregator modules
try:
    from .monitoring_aggregator_lg import (
        MetricsAggregator,
        IMetricsAggregator,
        AggregationStrategy,
        MetricType,
        AggregationPeriod,
        AggregationRule,
        AggregatedMetric,
        MetricsSnapshot,
        AggregationConfiguration,
        TimeSeriesProcessor,
        ITimeSeriesProcessor,
        DownsamplingMethod,
        WindowType,
        TrendDirection,
        DownsamplingConfiguration,
        WindowConfiguration,
        TimeSeriesPoint,
        ProcessedTimeSeries,
        RollingWindowResult,
        TimeSeriesStatistics
    )
except ImportError:
    pass

# Import training metrics modules
try:
    from .training_metrics_lg import (
        ILossCalculator,
        IMetricAggregator,
        IEarlyStopping,
        IMetricExporter,
        LossType,
        MetricType,
        AggregationStrategy,
        ExportFormat,
        EarlyStoppingCriteria,
        LossConfiguration,
        MetricConfiguration,
        AggregationConfiguration,
        EarlyStoppingConfiguration,
        ExportConfiguration,
        LossResult,
        MetricResult,
        AggregatedMetrics,
        EarlyStoppingResult,
        ExportResult,
        LossCalculator,
        TrainingLossTracker,
        ValidationLossTracker,
        CustomLossFunction,
        MetricAggregator,
        TrainingMetricsCollector,
        MetricStatistics,
        TimeSeriesMetrics,
        EarlyStopping,
        PatienceTracker,
        ImprovementDetector,
        StoppingCriteriaEvaluator,
        MetricExporter,
        JSONExporter,
        CSVExporter,
        TensorBoardExporter
    )
except ImportError:
    pass

__all__ = [
    # Resource Monitoring (Core Implementation)
    'HardwareMonitor',
    'GPUMonitor',
    'MemoryMonitor',
    'DiskMonitor',
    'ThermalMonitor',
    'IResourceMonitor',
    'ResourceMetrics',
    'MonitoringConfiguration',
    'MonitoringThresholds',
    'ResourceAlert',
    'AlertSeverity',
    'GPUMetrics',
    'GPUInfo',
    'CUDAInfo',
    'ROCmInfo',
    'MemoryMetrics',
    'MemoryAllocationPattern',
    'SwapUsageInfo',
    'DiskMetrics',
    'IOPerformanceMetrics',
    'StorageInfo',
    'ThermalMetrics',
    'TemperatureThresholds',
    'ThrottlingInfo',

    # Performance Optimization (Core Implementation)
    'OptimizationTrigger',
    'IOptimizationTrigger',
    'TriggerCondition',
    'TriggerType',
    'OptimizationAction',
    'TriggerConfiguration',
    'MetricThreshold',
    'TriggerEvent',
    'OptimizationContext',
    'MemoryPressureHandler',
    'IMemoryPressureHandler',
    'PressureLevel',
    'MemoryAction',
    'AllocationStrategy',
    'CleanupStrategy',
    'MemoryTier',
    'PressureConfiguration',
    'MemoryPressureEvent',
    'BatchSizeOptimizer',
    'IBatchSizeOptimizer',
    'BatchOptimizationStrategy',
    'ResourceConstraints',
    'BatchConfiguration',
    'OptimizationMetrics',
    'BatchSizeRecommendation',
    'PerformanceProfile',
    'CacheOptimizer',
    'ICacheOptimizer',
    'EvictionPolicy',
    'PrefetchStrategy',
    'CacheConfiguration',
    'AccessPattern',
    'CacheMetrics',
    'CacheOptimizationResult',
    'CacheLevel',

    # Monitoring Aggregator (Core Implementation)
    'MetricsAggregator',
    'IMetricsAggregator',
    'AggregationStrategy',
    'MetricType',
    'AggregationPeriod',
    'AggregationRule',
    'AggregatedMetric',
    'MetricsSnapshot',
    'AggregationConfiguration',

    # Time Series Processor (Core Implementation)
    'TimeSeriesProcessor',
    'ITimeSeriesProcessor',
    'DownsamplingMethod',
    'WindowType',
    'TrendDirection',
    'DownsamplingConfiguration',
    'WindowConfiguration',
    'TimeSeriesPoint',
    'ProcessedTimeSeries',
    'RollingWindowResult',
    'TimeSeriesStatistics',

    # Memory Allocation
    'AllocationStrategy',
    'IAllocationStrategy',
    'IDRAllocMode',
    'AllocationDecision',
    'HardwareProfile',
    'AllocationMetrics',
    'StrategyConfiguration',
    'AllocationResult',
    'MemoryTierManager',
    'IMemoryTierManager',
    'MemoryTierInfo',
    'TierCapacity',
    'TierBandwidth',
    'TierStatus',
    'TierConfiguration',
    'TierMetrics',
    'LayerDistributor',
    'ILayerDistributor',
    'LayerAllocationMap',
    'LayerInfo',
    'AccessPattern',
    'LayerPriority',
    'DistributionStrategy',
    'DistributionResult',

    # Memory Optimization
    'MemoryPressureDetector',
    'IMemoryPressureDetector',
    'PressureLevel',
    'PressureTrend',
    'MemoryMetrics',
    'PressureThreshold',
    'PredictionModel',
    'AllocationHistory',
    'PressureEvent',
    'AdaptiveReallocator',
    'IAdaptiveReallocator',
    'ReallocationStrategy',
    'PerformanceMetrics',
    'ResourceAvailability',
    'ReallocationDecision',
    'AdaptationTrigger',
    'ReallocationResult',
    'OptimizationTarget',
    'FragmentationManager',
    'IFragmentationManager',
    'FragmentationLevel',
    'DefragmentationStrategy',
    'MemoryPool',
    'FragmentationMetrics',
    'DefragmentationResult',
    'PoolConfiguration',
    'FragmentationEvent',

    # NVMe Virtual Memory
    'SwapController',
    'ISwapController',
    'SwapRequest',
    'SwapResult',
    'SwapStatus',
    'SwapConfiguration',
    'SwapMetrics',
    'SwapPolicy',
    'SwapPriority',
    'PageManager',
    'IPageManager',
    'PageInfo',
    'PageStatus',
    'PageAllocation',
    'PageConfiguration',
    'PageMetrics',
    'PageMapping',
    'PagePool',

    # Embedding Generation
    'DocumentEmbedder',
    'BatchProcessor',
    'EmbeddingCache',
    'IDocumentEmbedder',
    'IBatchProcessor',
    'IEmbeddingCache',
    'EmbeddingResult',
    'EmbeddingMetadata',
    'BatchProcessingResult',
    'CacheResult',
    'EmbeddingConfig',
    'BatchConfig',
    'CacheConfig',
    'EmbeddingStatus',
    'BatchStatus',
    'CacheStatus',
    'EmbeddingModel',
    'VectorDimensions',

    # Hybrid Search
    'SemanticSearcher',
    'KeywordSearcher',
    'ResultFusion',
    'ISemanticSearcher',
    'IKeywordSearcher',
    'IResultFusion',
    'SearchResultItem',
    'SemanticSearchResult',
    'KeywordSearchResult',
    'HybridSearchResult',
    'SemanticSearchConfig',
    'KeywordSearchConfig',
    'FusionConfig',
    'HybridSearchConfig',
    'SearchType',
    'FusionStrategy',
    'SearchStatus',
    'RankingMethod',
    'VectorEmbedder',
    'SimilarityMatcher',
    'SemanticRanker',
    'BM25Calculator',
    'InvertedIndexBuilder',
    'TermProcessor',
    'ScoreNormalizer',
    'RankFuser',
    'DiversityOptimizer',

    # Query Processor
    'QueryParser',
    'QueryExpander',
    'QueryOptimizer',
    'IQueryParser',
    'IQueryExpander',
    'IQueryOptimizer',
    'QueryType',
    'QueryOperator',
    'FieldType',
    'ExpansionMethod',
    'OptimizationStrategy',
    'QueryStatus',
    'QueryFilter',
    'QueryTerm',
    'ParsedQuery',
    'ExpandedTerm',
    'QueryExpansionResult',
    'ExecutionPlan',
    'IndexStatistics',
    'QueryOptimizationResult',
    'QueryParsingConfig',
    'QueryExpansionConfig',
    'QueryOptimizationConfig',
    'BooleanQueryParser',
    'PhraseQueryParser',
    'FieldQueryParser',
    'FilterParser',
    'OperatorParser',
    'SynonymExpander',
    'SemanticExpander',
    'StemExpander',
    'ContextualExpander',
    'DomainExpander',
    'CostEstimator',
    'ExecutionPlanner',
    'IndexAnalyzer',
    'StatisticsCollector',
    'QueryRewriter',

    # Training Metrics
    'ILossCalculator',
    'IMetricAggregator',
    'IEarlyStopping',
    'IMetricExporter',
    'LossType',
    'MetricType',
    'AggregationStrategy',
    'ExportFormat',
    'EarlyStoppingCriteria',
    'LossConfiguration',
    'MetricConfiguration',
    'AggregationConfiguration',
    'EarlyStoppingConfiguration',
    'ExportConfiguration',
    'LossResult',
    'MetricResult',
    'AggregatedMetrics',
    'EarlyStoppingResult',
    'ExportResult',
    'LossCalculator',
    'TrainingLossTracker',
    'ValidationLossTracker',
    'CustomLossFunction',
    'MetricAggregator',
    'TrainingMetricsCollector',
    'MetricStatistics',
    'TimeSeriesMetrics',
    'EarlyStopping',
    'PatienceTracker',
    'ImprovementDetector',
    'StoppingCriteriaEvaluator',
    'MetricExporter',
    'JSONExporter',
    'CSVExporter',
    'TensorBoardExporter'
]

# Import event system modules
try:
    from .event_system_lg import (
        EventBus,
        EventBusConfig,
        EventBusMetrics,
        EventBusResult,
        EventDispatcher,
        EventRouter,
        EventSubscriptionManager,
        EventDeliveryGuarantee,
        StateSynchronizer,
        StateChangeDetector,
        StateUpdatePropagator,
        ConflictResolver,
        StateUpdate,
        SynchronizationResult
    )
except ImportError:
    pass
