"""
Module: base_interfaces
Description: Base interfaces and common data structures for model optimization modules
Phase: 4
Location: /src/modules/logic/model_optimization_lg/base_interfaces.py
"""

# Standard library imports
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple, Set
import asyncio

# Third-party imports
import numpy as np
import torch


class QuantizationType(Enum):
    """Supported quantization types."""
    INT4 = "int4"
    INT8 = "int8"
    FP16 = "fp16"
    DYNAMIC = "dynamic"
    STATIC = "static"


class CompressionAlgorithm(Enum):
    """Supported compression algorithms."""
    GZIP = "gzip"
    LZMA = "lzma"
    BZIP2 = "bzip2"
    ZSTD = "zstd"
    LZ4 = "lz4"


class OptimizationLevel(Enum):
    """Optimization levels for model conversion."""
    BASIC = "basic"
    STANDARD = "standard"
    AGGRESSIVE = "aggressive"
    MAXIMUM = "maximum"


class ValidationMetric(Enum):
    """Metrics for model validation."""
    ACCURACY = "accuracy"
    PERPLEXITY = "perplexity"
    BLEU_SCORE = "bleu_score"
    ROUGE_SCORE = "rouge_score"
    F1_SCORE = "f1_score"
    INFERENCE_TIME = "inference_time"
    MEMORY_USAGE = "memory_usage"


class ModelFormat(Enum):
    """Supported model formats."""
    PYTORCH = "pytorch"
    ONNX = "onnx"
    TENSORRT = "tensorrt"
    OPENVINO = "openvino"
    COREML = "coreml"


@dataclass
class QuantizationConfig:
    """Configuration for model quantization."""
    quantization_type: QuantizationType = QuantizationType.INT8
    calibration_dataset_size: int = 1000
    enable_dynamic_quantization: bool = True
    preserve_accuracy_threshold: float = 0.95
    target_compression_ratio: float = 4.0
    optimization_level: OptimizationLevel = OptimizationLevel.STANDARD
    quantize_embeddings: bool = True
    quantize_attention: bool = True
    quantize_feedforward: bool = True
    custom_quantization_schemes: Dict[str, Any] = field(default_factory=dict)
    calibration_method: str = "entropy"
    batch_size: int = 32
    num_calibration_batches: int = 100


@dataclass
class ONNXConversionConfig:
    """Configuration for ONNX model conversion."""
    opset_version: int = 17
    dynamic_axes: Dict[str, Dict[int, str]] = field(default_factory=dict)
    optimization_level: OptimizationLevel = OptimizationLevel.STANDARD
    enable_optimization: bool = True
    target_device: str = "cpu"
    precision: str = "fp32"
    batch_size: Optional[int] = None
    sequence_length: Optional[int] = None
    enable_graph_optimization: bool = True
    enable_constant_folding: bool = True
    enable_redundant_node_elimination: bool = True
    custom_operators: List[str] = field(default_factory=list)
    export_params: bool = True
    do_constant_folding: bool = True


@dataclass
class ValidationConfig:
    """Configuration for model validation."""
    validation_metrics: List[ValidationMetric] = field(default_factory=lambda: [
        ValidationMetric.ACCURACY, ValidationMetric.INFERENCE_TIME
    ])
    test_dataset_size: int = 1000
    batch_size: int = 32
    max_sequence_length: int = 512
    tolerance_threshold: float = 0.05
    performance_threshold: float = 0.9
    memory_threshold_mb: float = 1024.0
    inference_time_threshold_ms: float = 100.0
    enable_statistical_testing: bool = True
    confidence_level: float = 0.95
    num_validation_runs: int = 5
    warmup_runs: int = 3
    enable_profiling: bool = True


@dataclass
class CompressionConfig:
    """Configuration for model compression."""
    algorithm: CompressionAlgorithm = CompressionAlgorithm.ZSTD
    compression_level: int = 6
    enable_parallel_compression: bool = True
    chunk_size_mb: int = 64
    preserve_metadata: bool = True
    verify_integrity: bool = True
    target_compression_ratio: Optional[float] = None
    max_compression_time_seconds: int = 300
    enable_delta_compression: bool = False
    compression_dictionary: Optional[Path] = None
    custom_compression_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelMetrics:
    """Metrics for model performance evaluation."""
    accuracy: float = 0.0
    perplexity: float = 0.0
    inference_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    model_size_mb: float = 0.0
    throughput_tokens_per_second: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    gpu_utilization_percent: float = 0.0
    cpu_utilization_percent: float = 0.0
    custom_metrics: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class QuantizationResult:
    """Result of model quantization operation."""
    success: bool
    quantized_model_path: Path
    original_model_size_mb: float
    quantized_model_size_mb: float
    compression_ratio: float
    quantization_config: QuantizationConfig
    performance_metrics: ModelMetrics
    quantization_time_seconds: float
    accuracy_degradation: float = 0.0
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class ONNXConversionResult:
    """Result of ONNX model conversion operation."""
    success: bool
    onnx_model_path: Path
    original_model_path: Path
    conversion_config: ONNXConversionConfig
    model_size_mb: float
    conversion_time_seconds: float
    opset_version: int
    input_shapes: Dict[str, Tuple[int, ...]]
    output_shapes: Dict[str, Tuple[int, ...]]
    optimization_applied: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class ValidationResult:
    """Result of model validation operation."""
    success: bool
    validation_config: ValidationConfig
    original_metrics: ModelMetrics
    optimized_metrics: ModelMetrics
    performance_degradation: float
    validation_time_seconds: float
    passed_tests: List[str] = field(default_factory=list)
    failed_tests: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class CompressionResult:
    """Result of model compression operation."""
    success: bool
    compressed_model_path: Path
    original_model_size_mb: float
    compressed_model_size_mb: float
    compression_ratio: float
    compression_config: CompressionConfig
    compression_time_seconds: float
    decompression_time_seconds: float = 0.0
    integrity_verified: bool = True
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now())


# Base Interfaces

class IQuantizationEngine(ABC):
    """Base interface for model quantization engines."""

    @abstractmethod
    async def quantize_model(self, model_path: Path, output_path: Path,
                           config: Optional[QuantizationConfig] = None) -> QuantizationResult:
        """
        Quantize a model using specified configuration.

        Args:
            model_path: Path to the original model
            output_path: Path for the quantized model
            config: Optional quantization configuration

        Returns:
            QuantizationResult with quantization details
        """
        pass

    @abstractmethod
    def get_supported_quantization_types(self) -> List[QuantizationType]:
        """Get list of supported quantization types."""
        pass

    @abstractmethod
    async def calibrate_quantization(self, model_path: Path, calibration_data: Any,
                                   config: QuantizationConfig) -> Dict[str, Any]:
        """
        Calibrate quantization parameters using calibration data.

        Args:
            model_path: Path to the model
            calibration_data: Calibration dataset
            config: Quantization configuration

        Returns:
            Calibration parameters
        """
        pass


class IONNXConverter(ABC):
    """Base interface for ONNX model converters."""

    @abstractmethod
    async def convert_to_onnx(self, model_path: Path, output_path: Path,
                            config: Optional[ONNXConversionConfig] = None) -> ONNXConversionResult:
        """
        Convert a model to ONNX format.

        Args:
            model_path: Path to the original model
            output_path: Path for the ONNX model
            config: Optional conversion configuration

        Returns:
            ONNXConversionResult with conversion details
        """
        pass

    @abstractmethod
    def validate_onnx_model(self, onnx_model_path: Path) -> bool:
        """
        Validate ONNX model structure and compatibility.

        Args:
            onnx_model_path: Path to ONNX model

        Returns:
            True if model is valid
        """
        pass

    @abstractmethod
    def get_model_info(self, model_path: Path) -> Dict[str, Any]:
        """
        Get information about the model structure.

        Args:
            model_path: Path to the model

        Returns:
            Model information dictionary
        """
        pass


class IOptimizationValidator(ABC):
    """Base interface for optimization validators."""

    @abstractmethod
    async def validate_optimization(self, original_model_path: Path,
                                  optimized_model_path: Path,
                                  config: Optional[ValidationConfig] = None) -> ValidationResult:
        """
        Validate that optimized model maintains acceptable performance.

        Args:
            original_model_path: Path to original model
            optimized_model_path: Path to optimized model
            config: Optional validation configuration

        Returns:
            ValidationResult with validation details
        """
        pass

    @abstractmethod
    async def benchmark_model(self, model_path: Path, test_data: Any,
                            config: ValidationConfig) -> ModelMetrics:
        """
        Benchmark model performance.

        Args:
            model_path: Path to the model
            test_data: Test dataset
            config: Validation configuration

        Returns:
            ModelMetrics with performance data
        """
        pass

    @abstractmethod
    def compare_models(self, original_metrics: ModelMetrics,
                      optimized_metrics: ModelMetrics) -> Dict[str, float]:
        """
        Compare performance between original and optimized models.

        Args:
            original_metrics: Original model metrics
            optimized_metrics: Optimized model metrics

        Returns:
            Comparison results
        """
        pass


class ICompressionEngine(ABC):
    """Base interface for model compression engines."""

    @abstractmethod
    async def compress_model(self, model_path: Path, output_path: Path,
                           config: Optional[CompressionConfig] = None) -> CompressionResult:
        """
        Compress a model using specified algorithm.

        Args:
            model_path: Path to the original model
            output_path: Path for the compressed model
            config: Optional compression configuration

        Returns:
            CompressionResult with compression details
        """
        pass

    @abstractmethod
    async def decompress_model(self, compressed_path: Path, output_path: Path) -> bool:
        """
        Decompress a compressed model.

        Args:
            compressed_path: Path to compressed model
            output_path: Path for decompressed model

        Returns:
            True if decompression successful
        """
        pass

    @abstractmethod
    def get_supported_algorithms(self) -> List[CompressionAlgorithm]:
        """Get list of supported compression algorithms."""
        pass

    @abstractmethod
    def estimate_compression_ratio(self, model_path: Path,
                                 algorithm: CompressionAlgorithm) -> float:
        """
        Estimate compression ratio for given algorithm.

        Args:
            model_path: Path to the model
            algorithm: Compression algorithm

        Returns:
            Estimated compression ratio
        """
        pass
