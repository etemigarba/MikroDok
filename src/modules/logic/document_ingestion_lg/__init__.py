"""
MikroDok Document Ingestion Package
Provides comprehensive document ingestion functionality including format detection, file validation, and batch processing.
"""

# Import format detector components
try:
    from .format_detector_lg import (
        FormatDetector,
        IFormatDetector,
        DocumentFormat,
        ProcessorType,
        FormatDetectionResult
    )
except ImportError:
    pass

# Import file validator components
try:
    from .file_validator_lg import (
        FileValidator,
        IFileValidator,
        FileValidationResult,
        FileValidationError,
        ValidationSeverity,
        ValidationCategory
    )
except ImportError:
    pass

# Import batch processor components
try:
    from .batch_processor_lg import (
        BatchProcessor,
        IBatchProcessor,
        BatchJob,
        BatchItem,
        BatchPriority,
        BatchStatus,
        ProcessingMode,
        BatchProcessingMetrics
    )
except ImportError:
    pass

__all__ = [
    # Format Detection
    'FormatDetector',
    'IFormatDetector',
    'DocumentFormat',
    'ProcessorType',
    'FormatDetectionResult',
    
    # File Validation
    'FileValidator',
    'IFileValidator',
    'FileValidationResult',
    'FileValidationError',
    'ValidationSeverity',
    'ValidationCategory',
    
    # Batch Processing
    'BatchProcessor',
    'IBatchProcessor',
    'BatchJob',
    'BatchItem',
    'BatchPriority',
    'BatchStatus',
    'ProcessingMode',
    'BatchProcessingMetrics'
]
