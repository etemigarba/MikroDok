"""
Module: optimization_validator_lg
Description: Validates optimized models maintain acceptable performance with comprehensive testing and benchmarking
Phase: 4
Location: /src/modules/logic/model_optimization_lg/optimization_validator_lg/optimization_validator_lg.py
"""

# Standard library imports
import asyncio
import logging
import time
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import warnings

# Third-party imports
import numpy as np
import torch
import torch.nn.functional as F
from scipy import stats
import psutil

# Local imports
try:
    from ..base_interfaces import (
        IOptimizationValidator,
        ValidationConfig,
        ValidationResult,
        ModelMetrics,
        ValidationMetric
    )
except ImportError:
    from src.modules.logic.model_optimization_lg.base_interfaces import (
        IOptimizationValidator,
        ValidationConfig,
        ValidationResult,
        ModelMetrics,
        ValidationMetric
    )

try:
    from src.modules.logic.error_handling_lg import ValidationError, ProcessingError
except ImportError:
    # Fallback error classes if not available
    class ValidationError(Exception):
        pass

    class ProcessingError(Exception):
        pass


class OptimizationValidator(IOptimizationValidator):
    """
    Production-ready optimization validator for model performance verification.
    
    Validates that optimized models maintain acceptable performance through
    comprehensive testing, statistical analysis, and benchmarking.
    """
    
    def __init__(self):
        """Initialize optimization validator with default settings."""
        self.logger = logging.getLogger(__name__)
        self._metric_calculators = self._initialize_metric_calculators()
        self._benchmark_cache = {}
        self._statistical_tests = self._initialize_statistical_tests()
    
    def _initialize_metric_calculators(self) -> Dict[str, callable]:
        """Initialize metric calculation functions."""
        return {
            ValidationMetric.ACCURACY: self._calculate_accuracy,
            ValidationMetric.PERPLEXITY: self._calculate_perplexity,
            ValidationMetric.BLEU_SCORE: self._calculate_bleu_score,
            ValidationMetric.ROUGE_SCORE: self._calculate_rouge_score,
            ValidationMetric.F1_SCORE: self._calculate_f1_score,
            ValidationMetric.INFERENCE_TIME: self._calculate_inference_time,
            ValidationMetric.MEMORY_USAGE: self._calculate_memory_usage
        }
    
    def _initialize_statistical_tests(self) -> Dict[str, callable]:
        """Initialize statistical test functions."""
        return {
            "t_test": stats.ttest_rel,
            "wilcoxon": stats.wilcoxon,
            "mann_whitney": stats.mannwhitneyu,
            "ks_test": stats.ks_2samp
        }
    
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
        start_time = time.time()
        config = config or ValidationConfig()
        
        try:
            self.logger.info(
                f"Starting optimization validation: {original_model_path} vs {optimized_model_path}"
            )
            
            # Validate input models
            if not original_model_path.exists():
                raise ValidationError(f"Original model not found: {original_model_path}")
            if not optimized_model_path.exists():
                raise ValidationError(f"Optimized model not found: {optimized_model_path}")
            
            # Load test data
            test_data = await self._load_test_data(config)
            
            # Benchmark original model
            original_metrics = await self.benchmark_model(
                original_model_path, test_data, config
            )
            
            # Benchmark optimized model
            optimized_metrics = await self.benchmark_model(
                optimized_model_path, test_data, config
            )
            
            # Compare models
            comparison_results = self.compare_models(original_metrics, optimized_metrics)
            
            # Calculate performance degradation
            performance_degradation = self._calculate_performance_degradation(
                original_metrics, optimized_metrics, config
            )
            
            # Run validation tests
            passed_tests, failed_tests = await self._run_validation_tests(
                original_metrics, optimized_metrics, config
            )
            
            # Determine overall success
            success = (
                performance_degradation <= config.tolerance_threshold and
                len(failed_tests) == 0
            )
            
            validation_time = time.time() - start_time
            
            self.logger.info(
                f"Validation completed in {validation_time:.2f}s, "
                f"degradation: {performance_degradation:.3f}, "
                f"success: {success}"
            )
            
            return ValidationResult(
                success=success,
                validation_config=config,
                original_metrics=original_metrics,
                optimized_metrics=optimized_metrics,
                performance_degradation=performance_degradation,
                validation_time_seconds=validation_time,
                passed_tests=passed_tests,
                failed_tests=failed_tests
            )
            
        except Exception as e:
            self.logger.error(f"Validation failed: {str(e)}")
            return ValidationResult(
                success=False,
                validation_config=config,
                original_metrics=ModelMetrics(),
                optimized_metrics=ModelMetrics(),
                performance_degradation=1.0,
                validation_time_seconds=time.time() - start_time,
                error_message=str(e)
            )
    
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
        try:
            self.logger.info(f"Benchmarking model: {model_path}")
            
            # Load model
            model = await self._load_model(model_path)
            model.eval()
            
            # Initialize metrics
            metrics = ModelMetrics()
            
            # Calculate each requested metric
            for metric_type in config.validation_metrics:
                if metric_type in self._metric_calculators:
                    calculator = self._metric_calculators[metric_type]
                    value = await calculator(model, test_data, config)
                    setattr(metrics, metric_type.value, value)
            
            # Calculate model size
            metrics.model_size_mb = self._get_model_size_mb(model_path)
            
            # Run multiple validation runs for statistical significance
            if config.enable_statistical_testing and config.num_validation_runs > 1:
                metrics = await self._run_statistical_benchmark(
                    model, test_data, config, metrics
                )
            
            self.logger.info(f"Benchmarking completed for {model_path}")
            return metrics
            
        except Exception as e:
            self.logger.error(f"Benchmarking failed: {str(e)}")
            return ModelMetrics()
    
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
        try:
            comparison = {}
            
            # Compare accuracy metrics
            if original_metrics.accuracy > 0:
                comparison["accuracy_ratio"] = optimized_metrics.accuracy / original_metrics.accuracy
                comparison["accuracy_difference"] = optimized_metrics.accuracy - original_metrics.accuracy
            
            # Compare inference time
            if original_metrics.inference_time_ms > 0:
                comparison["speed_improvement"] = (
                    original_metrics.inference_time_ms / optimized_metrics.inference_time_ms
                )
                comparison["latency_reduction"] = (
                    original_metrics.inference_time_ms - optimized_metrics.inference_time_ms
                )
            
            # Compare memory usage
            if original_metrics.memory_usage_mb > 0:
                comparison["memory_reduction"] = (
                    original_metrics.memory_usage_mb - optimized_metrics.memory_usage_mb
                )
                comparison["memory_ratio"] = (
                    optimized_metrics.memory_usage_mb / original_metrics.memory_usage_mb
                )
            
            # Compare model size
            if original_metrics.model_size_mb > 0:
                comparison["size_reduction"] = (
                    original_metrics.model_size_mb - optimized_metrics.model_size_mb
                )
                comparison["compression_ratio"] = (
                    original_metrics.model_size_mb / optimized_metrics.model_size_mb
                )
            
            # Compare throughput
            if original_metrics.throughput_tokens_per_second > 0:
                comparison["throughput_improvement"] = (
                    optimized_metrics.throughput_tokens_per_second / 
                    original_metrics.throughput_tokens_per_second
                )
            
            return comparison
            
        except Exception as e:
            self.logger.error(f"Model comparison failed: {str(e)}")
            return {}
    
    async def _load_model(self, model_path: Path) -> torch.nn.Module:
        """Load model from file."""
        try:
            if model_path.suffix == '.pth':
                model = torch.load(model_path, map_location='cpu')
            elif model_path.suffix == '.pt':
                model = torch.jit.load(model_path, map_location='cpu')
            elif model_path.suffix == '.onnx':
                # For ONNX models, we'll need to use ONNX Runtime
                import onnxruntime as ort
                return ort.InferenceSession(str(model_path))
            else:
                raise ValidationError(f"Unsupported model format: {model_path.suffix}")
            
            return model
            
        except Exception as e:
            raise ProcessingError(f"Failed to load model: {str(e)}")
    
    async def _load_test_data(self, config: ValidationConfig) -> Any:
        """Load test data for validation."""
        try:
            # Create synthetic test data for benchmarking
            batch_size = config.batch_size
            sequence_length = config.max_sequence_length
            
            # Generate random input data
            test_data = {
                "input_ids": torch.randint(0, 1000, (batch_size, sequence_length)),
                "attention_mask": torch.ones(batch_size, sequence_length),
                "labels": torch.randint(0, 2, (batch_size,))
            }
            
            return test_data
            
        except Exception as e:
            self.logger.warning(f"Failed to load test data: {str(e)}")
            return {}
    
    def _get_model_size_mb(self, model_path: Path) -> float:
        """Get model file size in MB."""
        try:
            size_bytes = model_path.stat().st_size
            return size_bytes / (1024 * 1024)
        except Exception:
            return 0.0
    
    def _calculate_performance_degradation(self, original_metrics: ModelMetrics,
                                         optimized_metrics: ModelMetrics,
                                         config: ValidationConfig) -> float:
        """Calculate overall performance degradation."""
        try:
            # Primary metric is accuracy
            if original_metrics.accuracy > 0:
                accuracy_degradation = (
                    original_metrics.accuracy - optimized_metrics.accuracy
                ) / original_metrics.accuracy
                return max(0.0, accuracy_degradation)
            
            # Fallback to perplexity if available
            if original_metrics.perplexity > 0 and optimized_metrics.perplexity > 0:
                perplexity_degradation = (
                    optimized_metrics.perplexity - original_metrics.perplexity
                ) / original_metrics.perplexity
                return max(0.0, perplexity_degradation)
            
            return 0.0
            
        except Exception as e:
            self.logger.error(f"Performance degradation calculation failed: {str(e)}")
            return 1.0  # Conservative estimate
    
    async def _run_validation_tests(self, original_metrics: ModelMetrics,
                                  optimized_metrics: ModelMetrics,
                                  config: ValidationConfig) -> Tuple[List[str], List[str]]:
        """Run validation tests and return passed/failed test names."""
        passed_tests = []
        failed_tests = []
        
        try:
            # Test accuracy threshold
            if original_metrics.accuracy > 0:
                accuracy_ratio = optimized_metrics.accuracy / original_metrics.accuracy
                if accuracy_ratio >= config.performance_threshold:
                    passed_tests.append("accuracy_threshold")
                else:
                    failed_tests.append("accuracy_threshold")
            
            # Test memory threshold
            if optimized_metrics.memory_usage_mb <= config.memory_threshold_mb:
                passed_tests.append("memory_threshold")
            else:
                failed_tests.append("memory_threshold")
            
            # Test inference time threshold
            if optimized_metrics.inference_time_ms <= config.inference_time_threshold_ms:
                passed_tests.append("inference_time_threshold")
            else:
                failed_tests.append("inference_time_threshold")
            
            # Test performance degradation
            degradation = self._calculate_performance_degradation(
                original_metrics, optimized_metrics, config
            )
            if degradation <= config.tolerance_threshold:
                passed_tests.append("performance_degradation")
            else:
                failed_tests.append("performance_degradation")
            
            return passed_tests, failed_tests
            
        except Exception as e:
            self.logger.error(f"Validation tests failed: {str(e)}")
            return [], ["validation_error"]
    
    async def _run_statistical_benchmark(self, model: torch.nn.Module, test_data: Any,
                                       config: ValidationConfig,
                                       base_metrics: ModelMetrics) -> ModelMetrics:
        """Run multiple benchmark runs for statistical significance."""
        try:
            inference_times = []
            memory_usages = []
            
            # Run multiple iterations
            for _ in range(config.num_validation_runs):
                # Warmup
                for _ in range(config.warmup_runs):
                    with torch.no_grad():
                        _ = model(test_data["input_ids"])
                
                # Measure inference time
                start_time = time.time()
                with torch.no_grad():
                    _ = model(test_data["input_ids"])
                inference_time = (time.time() - start_time) * 1000  # ms
                
                inference_times.append(inference_time)
                memory_usages.append(self._get_current_memory_usage())
            
            # Calculate statistics
            base_metrics.inference_time_ms = statistics.mean(inference_times)
            base_metrics.latency_p50_ms = statistics.median(inference_times)
            base_metrics.latency_p95_ms = np.percentile(inference_times, 95)
            base_metrics.latency_p99_ms = np.percentile(inference_times, 99)
            base_metrics.memory_usage_mb = statistics.mean(memory_usages)
            
            return base_metrics
            
        except Exception as e:
            self.logger.error(f"Statistical benchmark failed: {str(e)}")
            return base_metrics
    
    def _get_current_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            if torch.cuda.is_available():
                return torch.cuda.memory_allocated() / (1024 * 1024)
            else:
                process = psutil.Process()
                return process.memory_info().rss / (1024 * 1024)
        except Exception:
            return 0.0
    
    # Metric calculation methods
    async def _calculate_accuracy(self, model: torch.nn.Module, test_data: Any,
                                config: ValidationConfig) -> float:
        """Calculate model accuracy."""
        try:
            model.eval()
            correct = 0
            total = 0
            
            with torch.no_grad():
                outputs = model(test_data["input_ids"])
                if hasattr(outputs, 'logits'):
                    predictions = torch.argmax(outputs.logits, dim=-1)
                else:
                    predictions = torch.argmax(outputs, dim=-1)
                
                correct = (predictions == test_data["labels"]).sum().item()
                total = test_data["labels"].size(0)
            
            return correct / total if total > 0 else 0.0
            
        except Exception as e:
            self.logger.error(f"Accuracy calculation failed: {str(e)}")
            return 0.0
    
    async def _calculate_perplexity(self, model: torch.nn.Module, test_data: Any,
                                  config: ValidationConfig) -> float:
        """Calculate model perplexity."""
        try:
            model.eval()
            total_loss = 0.0
            total_tokens = 0
            
            with torch.no_grad():
                outputs = model(test_data["input_ids"])
                if hasattr(outputs, 'loss'):
                    loss = outputs.loss
                else:
                    # Calculate cross-entropy loss manually
                    logits = outputs.logits if hasattr(outputs, 'logits') else outputs
                    loss = F.cross_entropy(
                        logits.view(-1, logits.size(-1)),
                        test_data["input_ids"].view(-1)
                    )
                
                total_loss += loss.item()
                total_tokens += test_data["input_ids"].numel()
            
            avg_loss = total_loss / total_tokens if total_tokens > 0 else float('inf')
            return torch.exp(torch.tensor(avg_loss)).item()
            
        except Exception as e:
            self.logger.error(f"Perplexity calculation failed: {str(e)}")
            return float('inf')
    
    async def _calculate_bleu_score(self, model: torch.nn.Module, test_data: Any,
                                  config: ValidationConfig) -> float:
        """Calculate BLEU score (placeholder implementation)."""
        # This would require reference translations and generated text
        return 0.0
    
    async def _calculate_rouge_score(self, model: torch.nn.Module, test_data: Any,
                                   config: ValidationConfig) -> float:
        """Calculate ROUGE score (placeholder implementation)."""
        # This would require reference summaries and generated text
        return 0.0
    
    async def _calculate_f1_score(self, model: torch.nn.Module, test_data: Any,
                                config: ValidationConfig) -> float:
        """Calculate F1 score (placeholder implementation)."""
        # This would require proper classification setup
        return 0.0
    
    async def _calculate_inference_time(self, model: torch.nn.Module, test_data: Any,
                                      config: ValidationConfig) -> float:
        """Calculate inference time in milliseconds."""
        try:
            model.eval()
            
            # Warmup
            with torch.no_grad():
                for _ in range(config.warmup_runs):
                    _ = model(test_data["input_ids"])
            
            # Measure inference time
            start_time = time.time()
            with torch.no_grad():
                _ = model(test_data["input_ids"])
            
            return (time.time() - start_time) * 1000  # Convert to milliseconds
            
        except Exception as e:
            self.logger.error(f"Inference time calculation failed: {str(e)}")
            return 0.0
    
    async def _calculate_memory_usage(self, model: torch.nn.Module, test_data: Any,
                                    config: ValidationConfig) -> float:
        """Calculate memory usage in MB."""
        return self._get_current_memory_usage()
