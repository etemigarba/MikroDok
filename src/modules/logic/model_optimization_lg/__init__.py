"""
MikroDok Model Optimization Package
Provides comprehensive model optimization functionality including quantization, ONNX conversion, validation, and compression.
"""

# Import base interfaces and common structures
try:
    from .base_interfaces import (
        IQuantizationEngine,
        IONNXConverter,
        IOptimizationValidator,
        ICompressionEngine,
        QuantizationType,
        CompressionAlgorithm,
        OptimizationLevel,
        ValidationMetric,
        ModelFormat,
        QuantizationConfig,
        ONNXConversionConfig,
        ValidationConfig,
        CompressionConfig,
        ModelMetrics,
        QuantizationResult,
        ONNXConversionResult,
        ValidationResult,
        CompressionResult
    )
except ImportError:
    pass

# Import quantization engine components
try:
    from .quantization_engine_lg import QuantizationEngine
except ImportError:
    pass

# Import ONNX converter components
try:
    from .onnx_converter_lg import ONNXConverter
except ImportError:
    pass

# Import optimization validator components
try:
    from .optimization_validator_lg import OptimizationValidator
except ImportError:
    pass

# Import compression engine components
try:
    from .compression_engine_lg import CompressionEngine
except ImportError:
    pass

__all__ = [
    # Base Interfaces
    'IQuantizationEngine',
    'IONNXConverter',
    'IOptimizationValidator',
    'ICompressionEngine',
    
    # Enums
    'QuantizationType',
    'CompressionAlgorithm',
    'OptimizationLevel',
    'ValidationMetric',
    'ModelFormat',
    
    # Configuration Classes
    'QuantizationConfig',
    'ONNXConversionConfig',
    'ValidationConfig',
    'CompressionConfig',
    
    # Data Classes
    'ModelMetrics',
    'QuantizationResult',
    'ONNXConversionResult',
    'ValidationResult',
    'CompressionResult',
    
    # Implementation Classes
    'QuantizationEngine',
    'ONNXConverter',
    'OptimizationValidator',
    'CompressionEngine'
]
