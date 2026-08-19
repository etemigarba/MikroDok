"""
Module: batch_size_optimizer_lg
Description: Dynamically adjusts training batch sizes based on available resources and performance metrics
Phase: 2
Location: /src/modules/logic/performance_optimizer_lg/batch_size_optimizer_lg/
"""

# Standard library imports
import asyncio
import logging
import math
import statistics
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from collections import deque

# Local imports
from src.modules.logic.resource_monitor_lg import ResourceMetrics, MemoryMetrics, GPUMetrics
from src.modules.logic.logging_infrastructure_lg import get_logger


class BatchOptimizationStrategy(Enum):
    """Strategies for batch size optimization."""
    CONSERVATIVE = "CONSERVATIVE"
    AGGRESSIVE = "AGGRESSIVE"
    BALANCED = "BALANCED"
    MEMORY_CONSTRAINED = "MEMORY_CONSTRAINED"
    THROUGHPUT_OPTIMIZED = "THROUGHPUT_OPTIMIZED"
    LATENCY_OPTIMIZED = "LATENCY_OPTIMIZED"
    ADAPTIVE = "ADAPTIVE"


@dataclass
class ResourceConstraints:
    """Resource constraints for batch size optimization."""
    max_memory_usage_percent: float = 85.0
    max_gpu_memory_percent: float = 90.0
    min_available_memory_mb: float = 1024.0
    max_processing_time_seconds: float = 300.0
    thermal_limit_celsius: float = 85.0
    power_limit_watts: Optional[float] = None


@dataclass
class BatchConfiguration:
    """Configuration for batch size optimization."""
    min_batch_size: int = 1
    max_batch_size: int = 1024
    initial_batch_size: int = 32
    adjustment_step_size: int = 4
    optimization_interval_seconds: float = 30.0
    performance_window_size: int = 10
    stability_threshold: float = 0.05
    enable_predictive_scaling: bool = True
    enable_thermal_protection: bool = True


@dataclass
class OptimizationMetrics:
    """Metrics for batch size optimization."""
    timestamp: datetime
    batch_size: int
    processing_time_seconds: float
    throughput_samples_per_second: float
    memory_usage_percent: float
    gpu_utilization_percent: float
    gpu_memory_percent: float
    thermal_temperature_celsius: float
    efficiency_score: float


@dataclass
class BatchSizeRecommendation:
    """Recommendation for batch size adjustment."""
    recommended_batch_size: int
    current_batch_size: int
    adjustment_reason: str
    confidence_score: float
    expected_improvement_percent: float
    resource_utilization: Dict[str, float]
    risks: List[str] = field(default_factory=list)


@dataclass
class PerformanceProfile:
    """Performance profile for different batch sizes."""
    batch_size: int
    average_processing_time: float
    average_throughput: float
    memory_efficiency: float
    stability_score: float
    sample_count: int
    last_updated: datetime


class IBatchSizeOptimizer(ABC):
    """Interface for batch size optimization systems."""
    
    @abstractmethod
    async def optimize_batch_size(self, current_metrics: ResourceMetrics,
                                 current_batch_size: int) -> BatchSizeRecommendation:
        """Optimize batch size based on current metrics."""
        pass
    
    @abstractmethod
    def update_performance_metrics(self, batch_size: int, processing_time: float,
                                  throughput: float, resource_metrics: ResourceMetrics) -> None:
        """Update performance metrics for a specific batch size."""
        pass
    
    @abstractmethod
    def get_optimal_batch_size(self, constraints: ResourceConstraints) -> int:
        """Get the optimal batch size for given constraints."""
        pass
    
    @abstractmethod
    async def start_optimization(self) -> None:
        """Start continuous batch size optimization."""
        pass
    
    @abstractmethod
    async def stop_optimization(self) -> None:
        """Stop continuous batch size optimization."""
        pass


class BatchSizeOptimizer(IBatchSizeOptimizer):
    """
    Dynamically adjusts training batch sizes based on available resources and performance metrics.
    
    This class monitors system resources and performance to determine optimal batch sizes
    for training operations, balancing throughput, memory usage, and system stability.
    """
    
    def __init__(self, config: Optional[BatchConfiguration] = None,
                 constraints: Optional[ResourceConstraints] = None):
        """
        Initialize the batch size optimizer.
        
        Args:
            config: Configuration for optimization behavior
            constraints: Resource constraints for optimization
        """
        self._config = config or BatchConfiguration()
        self._constraints = constraints or ResourceConstraints()
        self._logger = get_logger(__name__)
        
        # Optimization state
        self._current_batch_size = self._config.initial_batch_size
        self._optimization_active = False
        self._optimization_task: Optional[asyncio.Task] = None
        self._lock = threading.RLock()
        
        # Performance tracking
        self._performance_history: deque = deque(maxlen=1000)
        self._performance_profiles: Dict[int, PerformanceProfile] = {}
        self._recent_metrics: deque = deque(maxlen=self._config.performance_window_size)
        
        # Optimization tracking
        self._optimization_history: deque = deque(maxlen=100)
        self._last_optimization_time: Optional[datetime] = None
        self._stability_tracker: deque = deque(maxlen=20)
        
        # Strategy management
        self._current_strategy = BatchOptimizationStrategy.BALANCED
        self._strategy_performance: Dict[BatchOptimizationStrategy, float] = {}
        
        # Performance analysis
        self._throughput_trend: deque = deque(maxlen=50)
        self._memory_trend: deque = deque(maxlen=50)
        self._efficiency_scores: deque = deque(maxlen=100)
        
        self._logger.info("Batch size optimizer initialized")
    
    async def optimize_batch_size(self, current_metrics: ResourceMetrics,
                                 current_batch_size: int) -> BatchSizeRecommendation:
        """Optimize batch size based on current metrics."""
        try:
            with self._lock:
                self._current_batch_size = current_batch_size
                
                # Analyze current performance
                performance_analysis = self._analyze_current_performance(current_metrics)
                
                # Check resource constraints
                constraint_analysis = self._analyze_resource_constraints(current_metrics)
                
                # Determine optimization strategy
                strategy = self._determine_optimization_strategy(current_metrics, performance_analysis)
                
                # Calculate recommended batch size
                recommended_size = self._calculate_optimal_batch_size(
                    current_batch_size, current_metrics, performance_analysis, constraint_analysis, strategy
                )
                
                # Create recommendation
                recommendation = self._create_recommendation(
                    current_batch_size, recommended_size, current_metrics, 
                    performance_analysis, constraint_analysis, strategy
                )
                
                # Track optimization
                self._track_optimization(recommendation)
                
                return recommendation
                
        except Exception as e:
            self._logger.error(f"Error optimizing batch size: {e}")
            return BatchSizeRecommendation(
                recommended_batch_size=current_batch_size,
                current_batch_size=current_batch_size,
                adjustment_reason="Error in optimization",
                confidence_score=0.0,
                expected_improvement_percent=0.0,
                resource_utilization={}
            )
    
    def update_performance_metrics(self, batch_size: int, processing_time: float,
                                  throughput: float, resource_metrics: ResourceMetrics) -> None:
        """Update performance metrics for a specific batch size."""
        try:
            current_time = datetime.now(timezone.utc)
            
            # Calculate efficiency score
            efficiency_score = self._calculate_efficiency_score(
                batch_size, processing_time, throughput, resource_metrics
            )
            
            # Create metrics entry
            metrics = OptimizationMetrics(
                timestamp=current_time,
                batch_size=batch_size,
                processing_time_seconds=processing_time,
                throughput_samples_per_second=throughput,
                memory_usage_percent=getattr(resource_metrics.memory, 'usage_percent', 0.0),
                gpu_utilization_percent=getattr(resource_metrics.gpu, 'utilization_percent', 0.0),
                gpu_memory_percent=getattr(resource_metrics.gpu, 'memory_percent', 0.0),
                thermal_temperature_celsius=getattr(resource_metrics.thermal, 'cpu_temperature_celsius', 0.0),
                efficiency_score=efficiency_score
            )
            
            with self._lock:
                # Add to history
                self._performance_history.append(metrics)
                self._recent_metrics.append(metrics)
                
                # Update performance profile
                self._update_performance_profile(batch_size, metrics)
                
                # Update trends
                self._throughput_trend.append(throughput)
                if hasattr(resource_metrics, 'memory') and resource_metrics.memory:
                    self._memory_trend.append(resource_metrics.memory.usage_percent)
                self._efficiency_scores.append(efficiency_score)
            
            self._logger.debug(f"Updated performance metrics for batch size {batch_size}: "
                             f"throughput={throughput:.2f}, efficiency={efficiency_score:.3f}")
            
        except Exception as e:
            self._logger.error(f"Error updating performance metrics: {e}")
    
    def get_optimal_batch_size(self, constraints: ResourceConstraints) -> int:
        """Get the optimal batch size for given constraints."""
        try:
            with self._lock:
                if not self._performance_profiles:
                    return self._config.initial_batch_size
                
                # Find the best performing batch size within constraints
                best_batch_size = self._config.initial_batch_size
                best_score = 0.0
                
                for batch_size, profile in self._performance_profiles.items():
                    if self._meets_constraints(profile, constraints):
                        score = self._calculate_profile_score(profile)
                        if score > best_score:
                            best_score = score
                            best_batch_size = batch_size
                
                return best_batch_size
                
        except Exception as e:
            self._logger.error(f"Error getting optimal batch size: {e}")
            return self._config.initial_batch_size

    async def start_optimization(self) -> None:
        """Start continuous batch size optimization."""
        if self._optimization_active:
            self._logger.warning("Batch size optimization already running")
            return

        self._optimization_active = True
        self._optimization_task = asyncio.create_task(self._optimization_loop())
        self._logger.info("Batch size optimization started")

    async def stop_optimization(self) -> None:
        """Stop continuous batch size optimization."""
        if not self._optimization_active:
            return

        self._optimization_active = False
        if self._optimization_task:
            self._optimization_task.cancel()
            try:
                await self._optimization_task
            except asyncio.CancelledError:
                pass

        self._logger.info("Batch size optimization stopped")

    async def _optimization_loop(self) -> None:
        """Main optimization loop."""
        self._logger.info("Starting batch size optimization loop")

        while self._optimization_active:
            try:
                # This would typically get current metrics and optimize
                # For now, we'll skip the actual optimization in the loop
                await asyncio.sleep(self._config.optimization_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in optimization loop: {e}")
                await asyncio.sleep(5.0)

    def _analyze_current_performance(self, metrics: ResourceMetrics) -> Dict[str, Any]:
        """Analyze current performance characteristics."""
        try:
            analysis = {
                'memory_pressure': 0.0,
                'gpu_utilization': 0.0,
                'thermal_pressure': 0.0,
                'throughput_trend': 'stable',
                'efficiency_trend': 'stable',
                'stability_score': 1.0
            }

            # Memory analysis
            if hasattr(metrics, 'memory') and metrics.memory:
                analysis['memory_pressure'] = metrics.memory.usage_percent / 100.0

            # GPU analysis
            if hasattr(metrics, 'gpu') and metrics.gpu:
                analysis['gpu_utilization'] = metrics.gpu.utilization_percent / 100.0

            # Thermal analysis
            if hasattr(metrics, 'thermal') and metrics.thermal:
                temp = metrics.thermal.cpu_temperature_celsius
                analysis['thermal_pressure'] = min(1.0, max(0.0, (temp - 60) / 25))

            # Trend analysis
            if len(self._throughput_trend) >= 5:
                recent_throughput = list(self._throughput_trend)[-5:]
                if len(recent_throughput) >= 3:
                    trend_slope = self._calculate_trend_slope(recent_throughput)
                    if trend_slope > 0.1:
                        analysis['throughput_trend'] = 'increasing'
                    elif trend_slope < -0.1:
                        analysis['throughput_trend'] = 'decreasing'

            # Efficiency trend
            if len(self._efficiency_scores) >= 5:
                recent_efficiency = list(self._efficiency_scores)[-5:]
                if len(recent_efficiency) >= 3:
                    trend_slope = self._calculate_trend_slope(recent_efficiency)
                    if trend_slope > 0.05:
                        analysis['efficiency_trend'] = 'improving'
                    elif trend_slope < -0.05:
                        analysis['efficiency_trend'] = 'degrading'

            # Stability analysis
            if len(self._recent_metrics) >= 3:
                throughputs = [m.throughput_samples_per_second for m in self._recent_metrics]
                if throughputs:
                    cv = statistics.stdev(throughputs) / (statistics.mean(throughputs) + 1e-8)
                    analysis['stability_score'] = max(0.0, 1.0 - cv)

            return analysis

        except Exception as e:
            self._logger.error(f"Error analyzing performance: {e}")
            return {}

    def _analyze_resource_constraints(self, metrics: ResourceMetrics) -> Dict[str, Any]:
        """Analyze resource constraint violations."""
        try:
            constraints = {
                'memory_constraint_violation': False,
                'gpu_memory_constraint_violation': False,
                'thermal_constraint_violation': False,
                'available_memory_mb': 0.0,
                'constraint_severity': 0.0
            }

            violations = []

            # Memory constraints
            if hasattr(metrics, 'memory') and metrics.memory:
                memory_usage = metrics.memory.usage_percent
                if memory_usage > self._constraints.max_memory_usage_percent:
                    constraints['memory_constraint_violation'] = True
                    violations.append(memory_usage - self._constraints.max_memory_usage_percent)

                constraints['available_memory_mb'] = metrics.memory.available_ram_mb
                if metrics.memory.available_ram_mb < self._constraints.min_available_memory_mb:
                    constraints['memory_constraint_violation'] = True
                    violations.append(1.0)  # Normalized violation

            # GPU memory constraints
            if hasattr(metrics, 'gpu') and metrics.gpu:
                gpu_memory = metrics.gpu.memory_percent
                if gpu_memory > self._constraints.max_gpu_memory_percent:
                    constraints['gpu_memory_constraint_violation'] = True
                    violations.append(gpu_memory - self._constraints.max_gpu_memory_percent)

            # Thermal constraints
            if hasattr(metrics, 'thermal') and metrics.thermal:
                temp = metrics.thermal.cpu_temperature_celsius
                if temp > self._constraints.thermal_limit_celsius:
                    constraints['thermal_constraint_violation'] = True
                    violations.append((temp - self._constraints.thermal_limit_celsius) / 10.0)

            # Calculate overall constraint severity
            if violations:
                constraints['constraint_severity'] = min(1.0, max(violations) / 100.0)

            return constraints

        except Exception as e:
            self._logger.error(f"Error analyzing constraints: {e}")
            return {}

    def _determine_optimization_strategy(self, metrics: ResourceMetrics,
                                       performance_analysis: Dict[str, Any]) -> BatchOptimizationStrategy:
        """Determine the best optimization strategy for current conditions."""
        try:
            # Check for constraint violations
            memory_pressure = performance_analysis.get('memory_pressure', 0.0)
            thermal_pressure = performance_analysis.get('thermal_pressure', 0.0)

            # High pressure situations
            if memory_pressure > 0.9 or thermal_pressure > 0.9:
                return BatchOptimizationStrategy.CONSERVATIVE

            # Memory constrained
            if memory_pressure > 0.8:
                return BatchOptimizationStrategy.MEMORY_CONSTRAINED

            # Performance optimization
            throughput_trend = performance_analysis.get('throughput_trend', 'stable')
            efficiency_trend = performance_analysis.get('efficiency_trend', 'stable')

            if throughput_trend == 'decreasing' or efficiency_trend == 'degrading':
                return BatchOptimizationStrategy.CONSERVATIVE
            elif throughput_trend == 'increasing' and efficiency_trend == 'improving':
                return BatchOptimizationStrategy.AGGRESSIVE

            # Default to balanced approach
            return BatchOptimizationStrategy.BALANCED

        except Exception as e:
            self._logger.error(f"Error determining strategy: {e}")
            return BatchOptimizationStrategy.BALANCED

    def _calculate_optimal_batch_size(self, current_batch_size: int, metrics: ResourceMetrics,
                                    performance_analysis: Dict[str, Any],
                                    constraint_analysis: Dict[str, Any],
                                    strategy: BatchOptimizationStrategy) -> int:
        """Calculate the optimal batch size based on analysis."""
        try:
            # Start with current batch size
            recommended_size = current_batch_size

            # Apply strategy-specific adjustments
            if strategy == BatchOptimizationStrategy.CONSERVATIVE:
                # Reduce batch size to be safe
                adjustment = -max(1, current_batch_size // 8)
            elif strategy == BatchOptimizationStrategy.AGGRESSIVE:
                # Increase batch size for better throughput
                adjustment = max(1, current_batch_size // 4)
            elif strategy == BatchOptimizationStrategy.MEMORY_CONSTRAINED:
                # Reduce based on memory pressure
                memory_pressure = performance_analysis.get('memory_pressure', 0.0)
                reduction_factor = min(0.5, memory_pressure)
                adjustment = -max(1, int(current_batch_size * reduction_factor))
            elif strategy == BatchOptimizationStrategy.THROUGHPUT_OPTIMIZED:
                # Optimize for maximum throughput
                if performance_analysis.get('throughput_trend') == 'increasing':
                    adjustment = max(1, current_batch_size // 6)
                else:
                    adjustment = 0
            else:  # BALANCED
                # Make small adjustments based on trends
                if performance_analysis.get('efficiency_trend') == 'improving':
                    adjustment = max(1, current_batch_size // 8)
                elif performance_analysis.get('efficiency_trend') == 'degrading':
                    adjustment = -max(1, current_batch_size // 8)
                else:
                    adjustment = 0

            # Apply adjustment
            recommended_size = current_batch_size + adjustment

            # Ensure within bounds
            recommended_size = max(self._config.min_batch_size,
                                 min(self._config.max_batch_size, recommended_size))

            # Check constraint violations
            if constraint_analysis.get('memory_constraint_violation', False):
                recommended_size = min(recommended_size, current_batch_size - self._config.adjustment_step_size)

            if constraint_analysis.get('thermal_constraint_violation', False):
                recommended_size = min(recommended_size, current_batch_size - self._config.adjustment_step_size)

            return max(self._config.min_batch_size, recommended_size)

        except Exception as e:
            self._logger.error(f"Error calculating optimal batch size: {e}")
            return current_batch_size

    def _create_recommendation(self, current_batch_size: int, recommended_size: int,
                              metrics: ResourceMetrics, performance_analysis: Dict[str, Any],
                              constraint_analysis: Dict[str, Any],
                              strategy: BatchOptimizationStrategy) -> BatchSizeRecommendation:
        """Create a batch size recommendation."""
        try:
            # Calculate confidence score
            confidence = self._calculate_confidence_score(
                current_batch_size, recommended_size, performance_analysis, constraint_analysis
            )

            # Calculate expected improvement
            expected_improvement = self._estimate_improvement(
                current_batch_size, recommended_size, performance_analysis
            )

            # Determine adjustment reason
            if recommended_size > current_batch_size:
                reason = f"Increase batch size using {strategy.value} strategy for better throughput"
            elif recommended_size < current_batch_size:
                reason = f"Reduce batch size using {strategy.value} strategy due to resource constraints"
            else:
                reason = "Maintain current batch size - optimal performance detected"

            # Calculate resource utilization
            resource_utilization = {}
            if hasattr(metrics, 'memory') and metrics.memory:
                resource_utilization['memory'] = metrics.memory.usage_percent
            if hasattr(metrics, 'gpu') and metrics.gpu:
                resource_utilization['gpu_compute'] = metrics.gpu.utilization_percent
                resource_utilization['gpu_memory'] = metrics.gpu.memory_percent

            # Identify risks
            risks = []
            if constraint_analysis.get('memory_constraint_violation', False):
                risks.append("Memory usage approaching limits")
            if constraint_analysis.get('thermal_constraint_violation', False):
                risks.append("Thermal throttling risk")
            if recommended_size > current_batch_size * 1.5:
                risks.append("Large batch size increase may cause instability")

            return BatchSizeRecommendation(
                recommended_batch_size=recommended_size,
                current_batch_size=current_batch_size,
                adjustment_reason=reason,
                confidence_score=confidence,
                expected_improvement_percent=expected_improvement,
                resource_utilization=resource_utilization,
                risks=risks
            )

        except Exception as e:
            self._logger.error(f"Error creating recommendation: {e}")
            return BatchSizeRecommendation(
                recommended_batch_size=current_batch_size,
                current_batch_size=current_batch_size,
                adjustment_reason="Error in recommendation generation",
                confidence_score=0.0,
                expected_improvement_percent=0.0,
                resource_utilization={}
            )

    def _calculate_efficiency_score(self, batch_size: int, processing_time: float,
                                   throughput: float, resource_metrics: ResourceMetrics) -> float:
        """Calculate efficiency score for a batch configuration."""
        try:
            # Base efficiency from throughput per resource usage
            base_efficiency = throughput / (processing_time + 1e-8)

            # Memory efficiency factor
            memory_factor = 1.0
            if hasattr(resource_metrics, 'memory') and resource_metrics.memory:
                memory_usage = resource_metrics.memory.usage_percent / 100.0
                memory_factor = 1.0 - (memory_usage ** 2)  # Penalize high memory usage

            # GPU efficiency factor
            gpu_factor = 1.0
            if hasattr(resource_metrics, 'gpu') and resource_metrics.gpu:
                gpu_util = resource_metrics.gpu.utilization_percent / 100.0
                # Optimal GPU utilization is around 80-90%
                if gpu_util < 0.5:
                    gpu_factor = gpu_util * 2  # Penalize low utilization
                elif gpu_util > 0.95:
                    gpu_factor = 2.0 - gpu_util  # Penalize over-utilization
                else:
                    gpu_factor = 1.0

            # Batch size efficiency (larger batches are generally more efficient)
            batch_factor = min(1.0, math.log(batch_size + 1) / math.log(64))

            # Combine factors
            efficiency_score = base_efficiency * memory_factor * gpu_factor * batch_factor

            # Normalize to 0-1 range
            return min(1.0, efficiency_score / 100.0)

        except Exception as e:
            self._logger.error(f"Error calculating efficiency score: {e}")
            return 0.5

    def _update_performance_profile(self, batch_size: int, metrics: OptimizationMetrics) -> None:
        """Update the performance profile for a specific batch size."""
        try:
            if batch_size not in self._performance_profiles:
                self._performance_profiles[batch_size] = PerformanceProfile(
                    batch_size=batch_size,
                    average_processing_time=metrics.processing_time_seconds,
                    average_throughput=metrics.throughput_samples_per_second,
                    memory_efficiency=1.0 - (metrics.memory_usage_percent / 100.0),
                    stability_score=1.0,
                    sample_count=1,
                    last_updated=metrics.timestamp
                )
            else:
                profile = self._performance_profiles[batch_size]

                # Update running averages
                alpha = 0.1  # Exponential moving average factor
                profile.average_processing_time = (
                    alpha * metrics.processing_time_seconds +
                    (1 - alpha) * profile.average_processing_time
                )
                profile.average_throughput = (
                    alpha * metrics.throughput_samples_per_second +
                    (1 - alpha) * profile.average_throughput
                )
                profile.memory_efficiency = (
                    alpha * (1.0 - metrics.memory_usage_percent / 100.0) +
                    (1 - alpha) * profile.memory_efficiency
                )

                profile.sample_count += 1
                profile.last_updated = metrics.timestamp

                # Update stability score based on recent variance
                if profile.sample_count >= 3:
                    recent_throughputs = [
                        m.throughput_samples_per_second for m in self._performance_history
                        if m.batch_size == batch_size
                    ][-10:]  # Last 10 samples

                    if len(recent_throughputs) >= 3:
                        cv = statistics.stdev(recent_throughputs) / (statistics.mean(recent_throughputs) + 1e-8)
                        profile.stability_score = max(0.0, 1.0 - cv)

        except Exception as e:
            self._logger.error(f"Error updating performance profile: {e}")

    def _calculate_trend_slope(self, values: List[float]) -> float:
        """Calculate the slope of a trend line for given values."""
        try:
            if len(values) < 2:
                return 0.0

            n = len(values)
            x_values = list(range(n))

            # Calculate linear regression slope
            sum_x = sum(x_values)
            sum_y = sum(values)
            sum_xy = sum(x * y for x, y in zip(x_values, values))
            sum_x2 = sum(x * x for x in x_values)

            denominator = n * sum_x2 - sum_x * sum_x
            if denominator == 0:
                return 0.0

            slope = (n * sum_xy - sum_x * sum_y) / denominator
            return slope

        except Exception:
            return 0.0

    def _meets_constraints(self, profile: PerformanceProfile, constraints: ResourceConstraints) -> bool:
        """Check if a performance profile meets the given constraints."""
        try:
            # Check processing time constraint
            if profile.average_processing_time > constraints.max_processing_time_seconds:
                return False

            # Check memory efficiency (inverse of memory usage)
            max_memory_efficiency = 1.0 - (constraints.max_memory_usage_percent / 100.0)
            if profile.memory_efficiency < max_memory_efficiency:
                return False

            # Check stability
            if profile.stability_score < 0.7:  # Minimum stability threshold
                return False

            return True

        except Exception:
            return False

    def _calculate_profile_score(self, profile: PerformanceProfile) -> float:
        """Calculate a score for a performance profile."""
        try:
            # Weighted combination of factors
            throughput_score = min(1.0, profile.average_throughput / 1000.0)  # Normalize
            efficiency_score = profile.memory_efficiency
            stability_score = profile.stability_score
            time_score = max(0.0, 1.0 - profile.average_processing_time / 300.0)  # Penalize long times

            # Weighted average
            score = (
                0.4 * throughput_score +
                0.3 * efficiency_score +
                0.2 * stability_score +
                0.1 * time_score
            )

            return score

        except Exception:
            return 0.0

    def _calculate_confidence_score(self, current_batch_size: int, recommended_size: int,
                                   performance_analysis: Dict[str, Any],
                                   constraint_analysis: Dict[str, Any]) -> float:
        """Calculate confidence score for a recommendation."""
        try:
            confidence = 0.5  # Base confidence

            # Increase confidence based on data availability
            if len(self._performance_history) > 10:
                confidence += 0.2

            # Increase confidence for small adjustments
            size_change = abs(recommended_size - current_batch_size) / current_batch_size
            if size_change < 0.25:  # Small change
                confidence += 0.2

            # Decrease confidence for constraint violations
            if constraint_analysis.get('constraint_severity', 0.0) > 0.5:
                confidence -= 0.3

            # Increase confidence for stable performance
            stability_score = performance_analysis.get('stability_score', 0.5)
            confidence += 0.3 * stability_score

            return max(0.0, min(1.0, confidence))

        except Exception:
            return 0.5

    def _estimate_improvement(self, current_batch_size: int, recommended_size: int,
                             performance_analysis: Dict[str, Any]) -> float:
        """Estimate expected performance improvement."""
        try:
            if recommended_size == current_batch_size:
                return 0.0

            # Base improvement estimate based on batch size change
            size_ratio = recommended_size / current_batch_size

            if size_ratio > 1.0:
                # Increasing batch size - estimate throughput improvement
                # Diminishing returns for larger batches
                improvement = min(20.0, 10.0 * math.log(size_ratio))
            else:
                # Decreasing batch size - estimate efficiency improvement
                # Better resource utilization
                improvement = min(15.0, 5.0 * (1.0 - size_ratio))

            # Adjust based on current trends
            if performance_analysis.get('efficiency_trend') == 'degrading':
                improvement *= 1.5  # More improvement expected
            elif performance_analysis.get('efficiency_trend') == 'improving':
                improvement *= 0.5  # Less improvement expected

            return max(0.0, improvement)

        except Exception:
            return 0.0

    def _track_optimization(self, recommendation: BatchSizeRecommendation) -> None:
        """Track optimization recommendation for analysis."""
        try:
            with self._lock:
                self._optimization_history.append(recommendation)
                self._last_optimization_time = datetime.now(timezone.utc)

                # Track stability
                if len(self._optimization_history) >= 2:
                    recent_recommendations = list(self._optimization_history)[-5:]
                    batch_sizes = [r.recommended_batch_size for r in recent_recommendations]
                    if len(batch_sizes) >= 3:
                        cv = statistics.stdev(batch_sizes) / (statistics.mean(batch_sizes) + 1e-8)
                        self._stability_tracker.append(cv)

        except Exception as e:
            self._logger.error(f"Error tracking optimization: {e}")

    def get_optimization_statistics(self) -> Dict[str, Any]:
        """Get statistics about batch size optimization."""
        with self._lock:
            current_stability = (
                statistics.mean(self._stability_tracker) if self._stability_tracker else 1.0
            )

            avg_efficiency = (
                statistics.mean(self._efficiency_scores) if self._efficiency_scores else 0.5
            )

            return {
                'current_batch_size': self._current_batch_size,
                'optimization_active': self._optimization_active,
                'performance_profiles': len(self._performance_profiles),
                'optimization_history': len(self._optimization_history),
                'current_strategy': self._current_strategy.value,
                'stability_score': max(0.0, 1.0 - current_stability),
                'average_efficiency': avg_efficiency,
                'last_optimization': self._last_optimization_time.isoformat() if self._last_optimization_time else None
            }
