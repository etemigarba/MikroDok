"""
Module: metrics_aggregator_lg
Description: Collects and aggregates performance metrics from all monitoring subsystems for unified reporting
Phase: 2
Location: /src/modules/logic/monitoring_aggregator_lg/metrics_aggregator_lg/
"""

# Standard library imports
import asyncio
import logging
import statistics
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from threading import Lock, RLock
from typing import Dict, List, Optional, Any, Callable, Union, Tuple

# Third-party imports
import psutil

# Local imports
from src.modules.logic.resource_monitor_lg import (
    ResourceMetrics,
    GPUMetrics,
    MemoryMetrics,
    DiskMetrics,
    ThermalMetrics,
    ResourceAlert,
    AlertSeverity
)


class AggregationStrategy(Enum):
    """Strategies for metric aggregation."""
    AVERAGE = "average"
    MAXIMUM = "maximum"
    MINIMUM = "minimum"
    SUM = "sum"
    MEDIAN = "median"
    PERCENTILE_95 = "percentile_95"
    PERCENTILE_99 = "percentile_99"
    LATEST = "latest"
    WEIGHTED_AVERAGE = "weighted_average"


class MetricType(Enum):
    """Types of metrics that can be aggregated."""
    RESOURCE = "resource"
    GPU = "gpu"
    MEMORY = "memory"
    DISK = "disk"
    THERMAL = "thermal"
    ALERT = "alert"
    CUSTOM = "custom"


class AggregationPeriod(Enum):
    """Time periods for metric aggregation."""
    REAL_TIME = "real_time"  # No aggregation
    MINUTE = "minute"
    FIVE_MINUTES = "five_minutes"
    FIFTEEN_MINUTES = "fifteen_minutes"
    HOUR = "hour"
    DAY = "day"


@dataclass
class AggregationRule:
    """Configuration for metric aggregation."""
    metric_name: str
    metric_type: MetricType
    strategy: AggregationStrategy
    period: AggregationPeriod
    weight_function: Optional[Callable[[datetime], float]] = None
    threshold_alert: Optional[float] = None
    enabled: bool = True


@dataclass
class AggregatedMetric:
    """Aggregated metric result."""
    metric_name: str
    metric_type: MetricType
    value: float
    timestamp: datetime
    period: AggregationPeriod
    strategy: AggregationStrategy
    sample_count: int
    confidence_score: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricsSnapshot:
    """Complete snapshot of all aggregated metrics."""
    timestamp: datetime
    resource_metrics: Optional[AggregatedMetric] = None
    gpu_metrics: List[AggregatedMetric] = field(default_factory=list)
    memory_metrics: Optional[AggregatedMetric] = None
    disk_metrics: Optional[AggregatedMetric] = None
    thermal_metrics: Optional[AggregatedMetric] = None
    alert_metrics: List[AggregatedMetric] = field(default_factory=list)
    custom_metrics: List[AggregatedMetric] = field(default_factory=list)
    total_metrics_count: int = 0
    aggregation_duration_ms: float = 0.0


@dataclass
class AggregationConfiguration:
    """Configuration for metrics aggregation."""
    enabled_rules: List[AggregationRule] = field(default_factory=list)
    max_history_size: int = 10000
    cleanup_interval_minutes: int = 60
    alert_threshold_cpu: float = 80.0
    alert_threshold_memory: float = 85.0
    alert_threshold_gpu: float = 90.0
    alert_threshold_thermal: float = 75.0
    enable_real_time_alerts: bool = True
    enable_trend_analysis: bool = True
    compression_enabled: bool = True
    compression_ratio: float = 0.1  # Keep 10% of historical data


class IMetricsAggregator(ABC):
    """Interface for metrics aggregation systems."""
    
    @abstractmethod
    async def start_aggregation(self) -> None:
        """Start the metrics aggregation process."""
        pass
    
    @abstractmethod
    async def stop_aggregation(self) -> None:
        """Stop the metrics aggregation process."""
        pass
    
    @abstractmethod
    def add_resource_metrics(self, metrics: ResourceMetrics) -> None:
        """Add resource metrics for aggregation."""
        pass
    
    @abstractmethod
    def add_gpu_metrics(self, metrics: GPUMetrics) -> None:
        """Add GPU metrics for aggregation."""
        pass
    
    @abstractmethod
    def add_memory_metrics(self, metrics: MemoryMetrics) -> None:
        """Add memory metrics for aggregation."""
        pass
    
    @abstractmethod
    def add_disk_metrics(self, metrics: DiskMetrics) -> None:
        """Add disk metrics for aggregation."""
        pass
    
    @abstractmethod
    def add_thermal_metrics(self, metrics: ThermalMetrics) -> None:
        """Add thermal metrics for aggregation."""
        pass
    
    @abstractmethod
    def get_aggregated_metrics(
        self, 
        period: AggregationPeriod = AggregationPeriod.MINUTE
    ) -> MetricsSnapshot:
        """Get aggregated metrics for a specific period."""
        pass
    
    @abstractmethod
    def get_metrics_history(
        self, 
        metric_type: MetricType,
        hours: int = 1
    ) -> List[AggregatedMetric]:
        """Get historical aggregated metrics."""
        pass
    
    @abstractmethod
    def configure_aggregation(self, config: AggregationConfiguration) -> None:
        """Configure aggregation rules and settings."""
        pass


class MetricsAggregator(IMetricsAggregator):
    """Advanced metrics aggregation system with configurable strategies and real-time processing."""
    
    def __init__(self, config: Optional[AggregationConfiguration] = None):
        """
        Initialize the metrics aggregator.
        
        Args:
            config: Aggregation configuration
        """
        self._config = config or AggregationConfiguration()
        self._logger = logging.getLogger(__name__)
        
        # Thread safety
        self._lock = RLock()
        self._aggregation_lock = Lock()
        
        # State management
        self._is_running = False
        self._aggregation_task: Optional[asyncio.Task] = None
        
        # Metric storage
        self._raw_metrics: Dict[MetricType, deque] = {
            metric_type: deque(maxlen=self._config.max_history_size)
            for metric_type in MetricType
        }
        
        # Aggregated metrics storage
        self._aggregated_metrics: Dict[AggregationPeriod, Dict[MetricType, deque]] = {
            period: {
                metric_type: deque(maxlen=1000)  # Store up to 1000 aggregated points per period
                for metric_type in MetricType
            }
            for period in AggregationPeriod
        }
        
        # Aggregation rules
        self._aggregation_rules: Dict[str, AggregationRule] = {}
        self._initialize_default_rules()
        
        # Performance tracking
        self._aggregation_stats = {
            'total_aggregations': 0,
            'average_duration_ms': 0.0,
            'last_aggregation_time': None,
            'errors_count': 0
        }
        
        # Alert tracking
        self._active_alerts: Dict[str, ResourceAlert] = {}
        self._alert_history: deque = deque(maxlen=1000)
        
        self._logger.info("MetricsAggregator initialized")

    def _initialize_default_rules(self) -> None:
        """Initialize default aggregation rules."""
        default_rules = [
            # CPU metrics
            AggregationRule(
                metric_name="cpu_usage_percent",
                metric_type=MetricType.RESOURCE,
                strategy=AggregationStrategy.AVERAGE,
                period=AggregationPeriod.MINUTE,
                threshold_alert=self._config.alert_threshold_cpu
            ),

            # Memory metrics
            AggregationRule(
                metric_name="memory_usage_percent",
                metric_type=MetricType.MEMORY,
                strategy=AggregationStrategy.AVERAGE,
                period=AggregationPeriod.MINUTE,
                threshold_alert=self._config.alert_threshold_memory
            ),

            # GPU metrics
            AggregationRule(
                metric_name="gpu_utilization_percent",
                metric_type=MetricType.GPU,
                strategy=AggregationStrategy.AVERAGE,
                period=AggregationPeriod.MINUTE,
                threshold_alert=self._config.alert_threshold_gpu
            ),

            # Thermal metrics
            AggregationRule(
                metric_name="highest_temperature",
                metric_type=MetricType.THERMAL,
                strategy=AggregationStrategy.MAXIMUM,
                period=AggregationPeriod.MINUTE,
                threshold_alert=self._config.alert_threshold_thermal
            ),

            # Disk I/O metrics
            AggregationRule(
                metric_name="disk_usage_percent",
                metric_type=MetricType.DISK,
                strategy=AggregationStrategy.AVERAGE,
                period=AggregationPeriod.MINUTE
            )
        ]

        for rule in default_rules:
            self._aggregation_rules[f"{rule.metric_type.value}_{rule.metric_name}"] = rule

    async def start_aggregation(self) -> None:
        """Start the metrics aggregation process."""
        try:
            if self._is_running:
                self._logger.warning("Aggregation already running")
                return

            with self._lock:
                self._is_running = True
                self._aggregation_task = asyncio.create_task(self._aggregation_loop())

            self._logger.info("Metrics aggregation started")

        except Exception as e:
            self._logger.error(f"Error starting aggregation: {e}")
            raise

    async def stop_aggregation(self) -> None:
        """Stop the metrics aggregation process."""
        try:
            if not self._is_running:
                return

            with self._lock:
                self._is_running = False

                if self._aggregation_task and not self._aggregation_task.done():
                    self._aggregation_task.cancel()
                    try:
                        await self._aggregation_task
                    except asyncio.CancelledError:
                        pass

                self._aggregation_task = None

            self._logger.info("Metrics aggregation stopped")

        except Exception as e:
            self._logger.error(f"Error stopping aggregation: {e}")
            raise

    def add_resource_metrics(self, metrics: ResourceMetrics) -> None:
        """Add resource metrics for aggregation."""
        try:
            with self._lock:
                self._raw_metrics[MetricType.RESOURCE].append(metrics)

            # Check for real-time alerts
            if self._config.enable_real_time_alerts:
                self._check_real_time_alerts(metrics, MetricType.RESOURCE)

        except Exception as e:
            self._logger.error(f"Error adding resource metrics: {e}")

    def add_gpu_metrics(self, metrics: GPUMetrics) -> None:
        """Add GPU metrics for aggregation."""
        try:
            with self._lock:
                self._raw_metrics[MetricType.GPU].append(metrics)

            # Check for real-time alerts
            if self._config.enable_real_time_alerts:
                self._check_real_time_alerts(metrics, MetricType.GPU)

        except Exception as e:
            self._logger.error(f"Error adding GPU metrics: {e}")

    def add_memory_metrics(self, metrics: MemoryMetrics) -> None:
        """Add memory metrics for aggregation."""
        try:
            with self._lock:
                self._raw_metrics[MetricType.MEMORY].append(metrics)

            # Check for real-time alerts
            if self._config.enable_real_time_alerts:
                self._check_real_time_alerts(metrics, MetricType.MEMORY)

        except Exception as e:
            self._logger.error(f"Error adding memory metrics: {e}")

    def add_disk_metrics(self, metrics: DiskMetrics) -> None:
        """Add disk metrics for aggregation."""
        try:
            with self._lock:
                self._raw_metrics[MetricType.DISK].append(metrics)

            # Check for real-time alerts
            if self._config.enable_real_time_alerts:
                self._check_real_time_alerts(metrics, MetricType.DISK)

        except Exception as e:
            self._logger.error(f"Error adding disk metrics: {e}")

    def add_thermal_metrics(self, metrics: ThermalMetrics) -> None:
        """Add thermal metrics for aggregation."""
        try:
            with self._lock:
                self._raw_metrics[MetricType.THERMAL].append(metrics)

            # Check for real-time alerts
            if self._config.enable_real_time_alerts:
                self._check_real_time_alerts(metrics, MetricType.THERMAL)

        except Exception as e:
            self._logger.error(f"Error adding thermal metrics: {e}")

    def get_aggregated_metrics(
        self,
        period: AggregationPeriod = AggregationPeriod.MINUTE
    ) -> MetricsSnapshot:
        """Get aggregated metrics for a specific period."""
        try:
            start_time = datetime.now(timezone.utc)

            with self._aggregation_lock:
                snapshot = MetricsSnapshot(timestamp=start_time)

                # Get aggregated metrics for each type
                for metric_type in MetricType:
                    if metric_type == MetricType.CUSTOM:
                        continue  # Skip custom metrics for now

                    aggregated = self._get_latest_aggregated_metric(metric_type, period)
                    if aggregated:
                        if metric_type == MetricType.RESOURCE:
                            snapshot.resource_metrics = aggregated
                        elif metric_type == MetricType.GPU:
                            snapshot.gpu_metrics.append(aggregated)
                        elif metric_type == MetricType.MEMORY:
                            snapshot.memory_metrics = aggregated
                        elif metric_type == MetricType.DISK:
                            snapshot.disk_metrics = aggregated
                        elif metric_type == MetricType.THERMAL:
                            snapshot.thermal_metrics = aggregated
                        elif metric_type == MetricType.ALERT:
                            snapshot.alert_metrics.append(aggregated)

                # Calculate total metrics count
                snapshot.total_metrics_count = sum(
                    len(self._raw_metrics[metric_type])
                    for metric_type in MetricType
                )

                # Calculate aggregation duration
                end_time = datetime.now(timezone.utc)
                snapshot.aggregation_duration_ms = (end_time - start_time).total_seconds() * 1000

                return snapshot

        except Exception as e:
            self._logger.error(f"Error getting aggregated metrics: {e}")
            return MetricsSnapshot(timestamp=datetime.now(timezone.utc))

    def get_metrics_history(
        self,
        metric_type: MetricType,
        hours: int = 1
    ) -> List[AggregatedMetric]:
        """Get historical aggregated metrics."""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            history = []

            with self._lock:
                # Get from all aggregation periods
                for period in AggregationPeriod:
                    if period == AggregationPeriod.REAL_TIME:
                        continue

                    period_metrics = self._aggregated_metrics[period][metric_type]
                    for metric in period_metrics:
                        if metric.timestamp >= cutoff_time:
                            history.append(metric)

            # Sort by timestamp
            history.sort(key=lambda x: x.timestamp)
            return history

        except Exception as e:
            self._logger.error(f"Error getting metrics history: {e}")
            return []

    def configure_aggregation(self, config: AggregationConfiguration) -> None:
        """Configure aggregation rules and settings."""
        try:
            with self._lock:
                self._config = config

                # Update aggregation rules
                self._aggregation_rules.clear()
                for rule in config.enabled_rules:
                    key = f"{rule.metric_type.value}_{rule.metric_name}"
                    self._aggregation_rules[key] = rule

                # If no custom rules provided, use defaults
                if not config.enabled_rules:
                    self._initialize_default_rules()

            self._logger.info(f"Aggregation configuration updated with {len(self._aggregation_rules)} rules")

        except Exception as e:
            self._logger.error(f"Error configuring aggregation: {e}")
            raise

    async def _aggregation_loop(self) -> None:
        """Main aggregation loop."""
        try:
            while self._is_running:
                try:
                    await self._perform_aggregation()
                    await asyncio.sleep(60)  # Aggregate every minute

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self._logger.error(f"Error in aggregation loop: {e}")
                    self._aggregation_stats['errors_count'] += 1
                    await asyncio.sleep(5)  # Brief pause before retry

        except Exception as e:
            self._logger.error(f"Fatal error in aggregation loop: {e}")
        finally:
            self._logger.info("Aggregation loop terminated")

    async def _perform_aggregation(self) -> None:
        """Perform metric aggregation for all configured rules."""
        start_time = datetime.now(timezone.utc)

        try:
            with self._aggregation_lock:
                for rule_key, rule in self._aggregation_rules.items():
                    if not rule.enabled:
                        continue

                    try:
                        aggregated = await self._aggregate_metric(rule)
                        if aggregated:
                            self._store_aggregated_metric(aggregated)

                    except Exception as e:
                        self._logger.error(f"Error aggregating {rule_key}: {e}")

                # Update performance stats
                duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                self._update_aggregation_stats(duration)

                # Perform cleanup if needed
                await self._cleanup_old_metrics()

        except Exception as e:
            self._logger.error(f"Error performing aggregation: {e}")
            raise

    async def _aggregate_metric(self, rule: AggregationRule) -> Optional[AggregatedMetric]:
        """Aggregate a specific metric according to its rule."""
        try:
            # Get raw metrics for the specified type
            raw_metrics = list(self._raw_metrics[rule.metric_type])
            if not raw_metrics:
                return None

            # Filter metrics based on period
            cutoff_time = self._get_period_cutoff_time(rule.period)
            filtered_metrics = [
                m for m in raw_metrics
                if hasattr(m, 'timestamp') and m.timestamp >= cutoff_time
            ]

            if not filtered_metrics:
                return None

            # Extract values for the specific metric
            values = self._extract_metric_values(filtered_metrics, rule.metric_name)
            if not values:
                return None

            # Apply aggregation strategy
            aggregated_value = self._apply_aggregation_strategy(values, rule.strategy, rule.weight_function)

            # Calculate confidence score
            confidence = min(1.0, len(values) / 10.0)  # Full confidence with 10+ samples

            return AggregatedMetric(
                metric_name=rule.metric_name,
                metric_type=rule.metric_type,
                value=aggregated_value,
                timestamp=datetime.now(timezone.utc),
                period=rule.period,
                strategy=rule.strategy,
                sample_count=len(values),
                confidence_score=confidence,
                metadata={
                    'rule_key': f"{rule.metric_type.value}_{rule.metric_name}",
                    'threshold_alert': rule.threshold_alert
                }
            )

        except Exception as e:
            self._logger.error(f"Error aggregating metric {rule.metric_name}: {e}")
            return None

    def _get_period_cutoff_time(self, period: AggregationPeriod) -> datetime:
        """Get cutoff time for aggregation period."""
        now = datetime.now(timezone.utc)

        if period == AggregationPeriod.MINUTE:
            return now - timedelta(minutes=1)
        elif period == AggregationPeriod.FIVE_MINUTES:
            return now - timedelta(minutes=5)
        elif period == AggregationPeriod.FIFTEEN_MINUTES:
            return now - timedelta(minutes=15)
        elif period == AggregationPeriod.HOUR:
            return now - timedelta(hours=1)
        elif period == AggregationPeriod.DAY:
            return now - timedelta(days=1)
        else:
            return now - timedelta(minutes=1)  # Default to 1 minute

    def _extract_metric_values(self, metrics: List[Any], metric_name: str) -> List[float]:
        """Extract specific metric values from metrics objects."""
        values = []

        for metric in metrics:
            try:
                if hasattr(metric, metric_name):
                    value = getattr(metric, metric_name)
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        values.append(float(value))
            except (AttributeError, TypeError, ValueError):
                continue

        return values

    def _apply_aggregation_strategy(
        self,
        values: List[float],
        strategy: AggregationStrategy,
        weight_function: Optional[Callable[[datetime], float]] = None
    ) -> float:
        """Apply aggregation strategy to values."""
        if not values:
            return 0.0

        try:
            if strategy == AggregationStrategy.AVERAGE:
                return statistics.mean(values)
            elif strategy == AggregationStrategy.MAXIMUM:
                return max(values)
            elif strategy == AggregationStrategy.MINIMUM:
                return min(values)
            elif strategy == AggregationStrategy.SUM:
                return sum(values)
            elif strategy == AggregationStrategy.MEDIAN:
                return statistics.median(values)
            elif strategy == AggregationStrategy.PERCENTILE_95:
                return self._calculate_percentile(values, 95)
            elif strategy == AggregationStrategy.PERCENTILE_99:
                return self._calculate_percentile(values, 99)
            elif strategy == AggregationStrategy.LATEST:
                return values[-1]
            elif strategy == AggregationStrategy.WEIGHTED_AVERAGE and weight_function:
                return self._calculate_weighted_average(values, weight_function)
            else:
                return statistics.mean(values)  # Default to average

        except Exception as e:
            self._logger.error(f"Error applying aggregation strategy {strategy}: {e}")
            return statistics.mean(values) if values else 0.0

    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = (percentile / 100.0) * (len(sorted_values) - 1)

        if index.is_integer():
            return sorted_values[int(index)]
        else:
            lower_index = int(index)
            upper_index = lower_index + 1
            weight = index - lower_index

            if upper_index < len(sorted_values):
                return sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight
            else:
                return sorted_values[lower_index]

    def _calculate_weighted_average(
        self,
        values: List[float],
        weight_function: Callable[[datetime], float]
    ) -> float:
        """Calculate weighted average using provided weight function."""
        if not values:
            return 0.0

        try:
            now = datetime.now(timezone.utc)
            weighted_sum = 0.0
            total_weight = 0.0

            for i, value in enumerate(values):
                # Assume values are in chronological order
                timestamp = now - timedelta(seconds=(len(values) - i - 1) * 60)
                weight = weight_function(timestamp)
                weighted_sum += value * weight
                total_weight += weight

            return weighted_sum / total_weight if total_weight > 0 else statistics.mean(values)

        except Exception as e:
            self._logger.error(f"Error calculating weighted average: {e}")
            return statistics.mean(values)

    def _store_aggregated_metric(self, metric: AggregatedMetric) -> None:
        """Store aggregated metric in the appropriate period bucket."""
        try:
            with self._lock:
                self._aggregated_metrics[metric.period][metric.metric_type].append(metric)

        except Exception as e:
            self._logger.error(f"Error storing aggregated metric: {e}")

    def _get_latest_aggregated_metric(
        self,
        metric_type: MetricType,
        period: AggregationPeriod
    ) -> Optional[AggregatedMetric]:
        """Get the latest aggregated metric for a type and period."""
        try:
            with self._lock:
                metrics = self._aggregated_metrics[period][metric_type]
                return metrics[-1] if metrics else None

        except Exception as e:
            self._logger.error(f"Error getting latest aggregated metric: {e}")
            return None

    def _check_real_time_alerts(self, metrics: Any, metric_type: MetricType) -> None:
        """Check for real-time alert conditions."""
        try:
            # Find applicable rules for this metric type
            for rule_key, rule in self._aggregation_rules.items():
                if rule.metric_type != metric_type or not rule.threshold_alert:
                    continue

                # Extract metric value
                if hasattr(metrics, rule.metric_name):
                    value = getattr(metrics, rule.metric_name)

                    if isinstance(value, (int, float)) and value > rule.threshold_alert:
                        alert_id = f"{metric_type.value}_{rule.metric_name}"

                        # Create or update alert
                        alert = ResourceAlert(
                            alert_id=alert_id,
                            severity=AlertSeverity.WARNING if value < rule.threshold_alert * 1.2 else AlertSeverity.CRITICAL,
                            message=f"{rule.metric_name} exceeded threshold: {value:.2f}% > {rule.threshold_alert}%",
                            timestamp=datetime.now(timezone.utc),
                            metric_name=rule.metric_name,
                            current_value=value,
                            threshold_value=rule.threshold_alert,
                            suggested_action=f"Monitor {rule.metric_name} usage and consider optimization"
                        )

                        self._active_alerts[alert_id] = alert
                        self._alert_history.append(alert)

                        self._logger.warning(f"Alert triggered: {alert.message}")
                    else:
                        # Clear alert if value is back to normal
                        alert_id = f"{metric_type.value}_{rule.metric_name}"
                        if alert_id in self._active_alerts:
                            del self._active_alerts[alert_id]

        except Exception as e:
            self._logger.error(f"Error checking real-time alerts: {e}")

    def _update_aggregation_stats(self, duration_ms: float) -> None:
        """Update aggregation performance statistics."""
        try:
            with self._lock:
                self._aggregation_stats['total_aggregations'] += 1
                self._aggregation_stats['last_aggregation_time'] = datetime.now(timezone.utc)

                # Update rolling average duration
                current_avg = self._aggregation_stats['average_duration_ms']
                total_count = self._aggregation_stats['total_aggregations']

                self._aggregation_stats['average_duration_ms'] = (
                    (current_avg * (total_count - 1) + duration_ms) / total_count
                )

        except Exception as e:
            self._logger.error(f"Error updating aggregation stats: {e}")

    async def _cleanup_old_metrics(self) -> None:
        """Clean up old metrics to prevent memory bloat."""
        try:
            if self._aggregation_stats['total_aggregations'] % self._config.cleanup_interval_minutes != 0:
                return

            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)

            with self._lock:
                # Clean up raw metrics
                for metric_type in MetricType:
                    raw_metrics = self._raw_metrics[metric_type]

                    # Keep only recent metrics
                    filtered_metrics = deque(maxlen=self._config.max_history_size)
                    for metric in raw_metrics:
                        if hasattr(metric, 'timestamp') and metric.timestamp >= cutoff_time:
                            filtered_metrics.append(metric)

                    self._raw_metrics[metric_type] = filtered_metrics

                # Clean up aggregated metrics
                for period in AggregationPeriod:
                    if period == AggregationPeriod.REAL_TIME:
                        continue

                    for metric_type in MetricType:
                        aggregated_metrics = self._aggregated_metrics[period][metric_type]

                        # Apply compression if enabled
                        if self._config.compression_enabled:
                            compressed_metrics = deque(maxlen=1000)
                            total_metrics = len(aggregated_metrics)
                            keep_count = max(1, int(total_metrics * self._config.compression_ratio))

                            # Keep the most recent metrics
                            for metric in list(aggregated_metrics)[-keep_count:]:
                                compressed_metrics.append(metric)

                            self._aggregated_metrics[period][metric_type] = compressed_metrics

                # Clean up old alerts
                self._alert_history = deque(
                    [alert for alert in self._alert_history if alert.timestamp >= cutoff_time],
                    maxlen=1000
                )

            self._logger.debug("Completed metrics cleanup")

        except Exception as e:
            self._logger.error(f"Error during metrics cleanup: {e}")

    def get_aggregation_stats(self) -> Dict[str, Any]:
        """Get aggregation performance statistics."""
        with self._lock:
            return {
                **self._aggregation_stats,
                'active_alerts_count': len(self._active_alerts),
                'total_raw_metrics': sum(len(self._raw_metrics[mt]) for mt in MetricType),
                'total_aggregated_metrics': sum(
                    sum(len(self._aggregated_metrics[period][mt]) for mt in MetricType)
                    for period in AggregationPeriod if period != AggregationPeriod.REAL_TIME
                ),
                'is_running': self._is_running
            }

    def get_active_alerts(self) -> List[ResourceAlert]:
        """Get currently active alerts."""
        with self._lock:
            return list(self._active_alerts.values())

    def get_alert_history(self, hours: int = 24) -> List[ResourceAlert]:
        """Get alert history for specified time period."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        with self._lock:
            return [
                alert for alert in self._alert_history
                if alert.timestamp >= cutoff_time
            ]
