"""
MikroDok Training Data Pipeline Package
Provides comprehensive training data pipeline functionality including data loading, augmentation, validation, and batch generation.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        IDataLoader,
        IDataAugmentation,
        IDataValidator,
        IBatchGenerator,
        DataFormat,
        AugmentationType,
        ValidationLevel,
        BatchStrategy,
        DataStatus,
        DataLoaderConfig,
        AugmentationConfig,
        ValidationConfig,
        BatchConfig,
        DataSample,
        DataBatch,
        LoadingResult,
        AugmentationResult,
        ValidationResult,
        BatchGenerationResult
    )
except ImportError:
    pass

# Import data loader components
try:
    from .data_loader_lg import (
        DataLoader,
        TrainingDataLoader,
        StreamingDataLoader,
        CachedDataLoader
    )
except ImportError:
    pass

# Import data augmentation components
try:
    from .data_augmentation_lg import (
        DataAugmentation,
        TextAugmenter,
        SynonymReplacer,
        NoiseInjector
    )
except ImportError:
    pass

# Import data validator components
try:
    from .data_validator_lg import (
        DataValidator,
        FormatValidator,
        QualityValidator,
        ConsistencyValidator
    )
except ImportError:
    pass

# Import batch generator components
try:
    from .batch_generator_lg import (
        BatchGenerator,
        SequentialBatchGenerator,
        RandomBatchGenerator,
        BalancedBatchGenerator
    )
except ImportError:
    pass

__all__ = [
    # Base interfaces and structures
    'IDataLoader',
    'IDataAugmentation',
    'IDataValidator',
    'IBatchGenerator',
    'DataFormat',
    'AugmentationType',
    'ValidationLevel',
    'BatchStrategy',
    'DataStatus',
    'DataLoaderConfig',
    'AugmentationConfig',
    'ValidationConfig',
    'BatchConfig',
    'DataSample',
    'DataBatch',
    'LoadingResult',
    'AugmentationResult',
    'ValidationResult',
    'BatchGenerationResult',
    
    # Data Loader
    'DataLoader',
    'TrainingDataLoader',
    'StreamingDataLoader',
    'CachedDataLoader',
    
    # Data Augmentation
    'DataAugmentation',
    'TextAugmenter',
    'SynonymReplacer',
    'NoiseInjector',
    
    # Data Validator
    'DataValidator',
    'FormatValidator',
    'QualityValidator',
    'ConsistencyValidator',
    
    # Batch Generator
    'BatchGenerator',
    'SequentialBatchGenerator',
    'RandomBatchGenerator',
    'BalancedBatchGenerator'
]
