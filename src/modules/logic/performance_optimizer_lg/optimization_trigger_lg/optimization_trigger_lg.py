"""
Module: optimization_trigger_lg
Description: Evaluates system metrics against thresholds and triggers appropriate optimization actions based on resource pressure
Phase: 2
Location: /src/modules/logic/performance_optimizer_lg/optimization_trigger_lg/
"""

# Standard library imports
import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Set, Tuple
from collections import defaultdict, deque

# Local imports
from src.modules.logic.resource_monitor_lg import (
    ResourceMetrics, 
    MemoryMetrics, 
    GPUMetrics, 
    ThermalMetrics,
    DiskMetrics
)
from src.modules.logic.logging_infrastructure_lg import get_logger


class TriggerType(Enum):
    """Types of optimization triggers."""
    MEMORY_PRESSURE = "MEMORY_PRESSURE"
    CPU_UTILIZATION = "CPU_UTILIZATION"
    GPU_UTILIZATION = "GPU_UTILIZATION"
    THERMAL_THROTTLING = "THERMAL_THROTTLING"
    DISK_IO_PRESSURE = "DISK_IO_PRESSURE"
    PERFORMANCE_DEGRADATION = "PERFORMANCE_DEGRADATION"
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
    BATCH_SIZE_ADJUSTMENT = "BATCH_SIZE_ADJUSTMENT"
    CACHE_PRESSURE = "CACHE_PRESSURE"


class TriggerCondition(Enum):
    """Conditions for trigger activation."""
    GREATER_THAN = "GREATER_THAN"
    LESS_THAN = "LESS_THAN"
    EQUALS = "EQUALS"
    GREATER_EQUAL = "GREATER_EQUAL"
    LESS_EQUAL = "LESS_EQUAL"
    TREND_INCREASING = "TREND_INCREASING"
    TREND_DECREASING = "TREND_DECREASING"
    SUSTAINED_HIGH = "SUSTAINED_HIGH"
    SUSTAINED_LOW = "SUSTAINED_LOW"


class OptimizationAction(Enum):
    """Actions that can be triggered for optimization."""
    REDUCE_BATCH_SIZE = "REDUCE_BATCH_SIZE"
    INCREASE_BATCH_SIZE = "INCREASE_BATCH_SIZE"
    ENABLE_MEMORY_CLEANUP = "ENABLE_MEMORY_CLEANUP"
    ADJUST_CACHE_SIZE = "ADJUST_CACHE_SIZE"
    THROTTLE_PROCESSING = "THROTTLE_PROCESSING"
    INCREASE_PARALLELISM = "INCREASE_PARALLELISM"
    REDUCE_PARALLELISM = "REDUCE_PARALLELISM"
    ENABLE_THERMAL_MANAGEMENT = "ENABLE_THERMAL_MANAGEMENT"
    OPTIMIZE_MEMORY_ALLOCATION = "OPTIMIZE_MEMORY_ALLOCATION"
    EMERGENCY_CLEANUP = "EMERGENCY_CLEANUP"


@dataclass
class MetricThreshold:
    """Defines a threshold for a specific metric."""
    metric_name: str
    threshold_value: float
    condition: TriggerCondition
    sustained_duration_seconds: float = 0.0
    cooldown_seconds: float = 60.0
    priority: int = 1  # Higher number = higher priority


@dataclass
class TriggerEvent:
    """Represents a triggered optimization event."""
    trigger_id: str
    trigger_type: TriggerType
    action: OptimizationAction
    timestamp: datetime
    metric_value: float
    threshold: MetricThreshold
    context: Dict[str, Any] = field(default_factory=dict)
    severity: float = 1.0  # 0.0 to 1.0


@dataclass
class OptimizationContext:
    """Context information for optimization decisions."""
    current_metrics: ResourceMetrics
    historical_metrics: List[ResourceMetrics]
    active_triggers: Set[str]
    recent_actions: List[TriggerEvent]
    system_load: float
    available_resources: Dict[str, float]


@dataclass
class TriggerConfiguration:
    """Configuration for optimization triggers."""
    enabled: bool = True
    monitoring_interval_seconds: float = 5.0
    history_retention_minutes: int = 60
    max_concurrent_actions: int = 3
    action_cooldown_seconds: float = 30.0
    enable_predictive_triggers: bool = True
    trend_analysis_window_minutes: int = 10
    emergency_thresholds_enabled: bool = True


class IOptimizationTrigger(ABC):
    """Interface for optimization trigger systems."""
    
    @abstractmethod
    async def start_monitoring(self) -> None:
        """Start the optimization trigger monitoring."""
        pass
    
    @abstractmethod
    async def stop_monitoring(self) -> None:
        """Stop the optimization trigger monitoring."""
        pass
    
    @abstractmethod
    def add_threshold(self, trigger_id: str, trigger_type: TriggerType,
                     threshold: MetricThreshold, action: OptimizationAction) -> None:
        """Add a new optimization threshold."""
        pass
    
    @abstractmethod
    def remove_threshold(self, trigger_id: str) -> None:
        """Remove an optimization threshold."""
        pass
    
    @abstractmethod
    async def evaluate_triggers(self, metrics: ResourceMetrics) -> List[TriggerEvent]:
        """Evaluate all triggers against current metrics."""
        pass
    
    @abstractmethod
    def register_action_handler(self, action: OptimizationAction, 
                               handler: Callable[[TriggerEvent, OptimizationContext], None]) -> None:
        """Register a handler for optimization actions."""
        pass


class OptimizationTrigger(IOptimizationTrigger):
    """
    Evaluates system metrics against thresholds and triggers appropriate optimization actions.
    
    This class monitors system resources and triggers optimization actions when
    predefined thresholds are exceeded or specific conditions are met.
    """
    
    def __init__(self, config: Optional[TriggerConfiguration] = None):
        """
        Initialize the optimization trigger system.
        
        Args:
            config: Configuration for trigger behavior
        """
        self._config = config or TriggerConfiguration()
        self._logger = get_logger(__name__)
        
        # Trigger management
        self._triggers: Dict[str, Tuple[TriggerType, MetricThreshold, OptimizationAction]] = {}
        self._action_handlers: Dict[OptimizationAction, Callable] = {}
        self._active_triggers: Set[str] = set()
        self._trigger_states: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # Monitoring state
        self._monitoring = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._lock = threading.RLock()
        
        # Metrics history
        self._metrics_history: deque = deque(maxlen=1000)
        self._recent_events: deque = deque(maxlen=100)
        
        # Cooldown tracking
        self._action_cooldowns: Dict[OptimizationAction, datetime] = {}
        self._trigger_cooldowns: Dict[str, datetime] = {}
        
        # Performance tracking
        self._evaluation_times: deque = deque(maxlen=100)
        
        self._logger.info("Optimization trigger system initialized")

    async def start_monitoring(self) -> None:
        """Start the optimization trigger monitoring."""
        if self._monitoring:
            self._logger.warning("Optimization trigger monitoring already running")
            return

        self._monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._logger.info("Optimization trigger monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop the optimization trigger monitoring."""
        if not self._monitoring:
            return

        self._monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        self._logger.info("Optimization trigger monitoring stopped")

    def add_threshold(self, trigger_id: str, trigger_type: TriggerType,
                     threshold: MetricThreshold, action: OptimizationAction) -> None:
        """Add a new optimization threshold."""
        with self._lock:
            self._triggers[trigger_id] = (trigger_type, threshold, action)
            self._trigger_states[trigger_id] = {
                'last_triggered': None,
                'sustained_start': None,
                'trend_values': deque(maxlen=20)
            }

        self._logger.info(f"Added optimization trigger: {trigger_id} -> {action.value}")

    def remove_threshold(self, trigger_id: str) -> None:
        """Remove an optimization threshold."""
        with self._lock:
            if trigger_id in self._triggers:
                del self._triggers[trigger_id]
                del self._trigger_states[trigger_id]
                self._active_triggers.discard(trigger_id)

        self._logger.info(f"Removed optimization trigger: {trigger_id}")

    async def evaluate_triggers(self, metrics: ResourceMetrics) -> List[TriggerEvent]:
        """Evaluate all triggers against current metrics."""
        start_time = time.time()
        triggered_events = []
        current_time = datetime.now(timezone.utc)

        try:
            with self._lock:
                # Add metrics to history
                self._metrics_history.append(metrics)

                # Evaluate each trigger
                for trigger_id, (trigger_type, threshold, action) in self._triggers.items():
                    try:
                        event = await self._evaluate_single_trigger(
                            trigger_id, trigger_type, threshold, action, metrics, current_time
                        )
                        if event:
                            triggered_events.append(event)
                    except Exception as e:
                        self._logger.error(f"Error evaluating trigger {trigger_id}: {e}")

            # Execute triggered actions
            for event in triggered_events:
                await self._execute_action(event, metrics)

            # Track performance
            evaluation_time = time.time() - start_time
            self._evaluation_times.append(evaluation_time)

            if triggered_events:
                self._logger.info(f"Triggered {len(triggered_events)} optimization actions")

            return triggered_events

        except Exception as e:
            self._logger.error(f"Error in trigger evaluation: {e}")
            return []

    def register_action_handler(self, action: OptimizationAction,
                               handler: Callable[[TriggerEvent, OptimizationContext], None]) -> None:
        """Register a handler for optimization actions."""
        with self._lock:
            self._action_handlers[action] = handler

        self._logger.info(f"Registered handler for action: {action.value}")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop for trigger evaluation."""
        self._logger.info("Starting optimization trigger monitoring loop")

        while self._monitoring:
            try:
                # This would typically get metrics from resource monitors
                # For now, we'll skip the actual monitoring in the loop
                await asyncio.sleep(self._config.monitoring_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(1.0)

    async def _evaluate_single_trigger(self, trigger_id: str, trigger_type: TriggerType,
                                     threshold: MetricThreshold, action: OptimizationAction,
                                     metrics: ResourceMetrics, current_time: datetime) -> Optional[TriggerEvent]:
        """Evaluate a single trigger against current metrics."""
        try:
            # Check cooldown
            if trigger_id in self._trigger_cooldowns:
                if current_time < self._trigger_cooldowns[trigger_id]:
                    return None

            # Get metric value
            metric_value = self._extract_metric_value(trigger_type, threshold.metric_name, metrics)
            if metric_value is None:
                return None

            # Update trend tracking
            trigger_state = self._trigger_states[trigger_id]
            trigger_state['trend_values'].append((current_time, metric_value))

            # Evaluate condition
            condition_met = self._evaluate_condition(threshold, metric_value, trigger_state, current_time)

            if condition_met:
                # Check action cooldown
                if action in self._action_cooldowns:
                    if current_time < self._action_cooldowns[action]:
                        return None

                # Create trigger event
                event = TriggerEvent(
                    trigger_id=trigger_id,
                    trigger_type=trigger_type,
                    action=action,
                    timestamp=current_time,
                    metric_value=metric_value,
                    threshold=threshold,
                    severity=self._calculate_severity(metric_value, threshold)
                )

                # Update cooldowns
                self._trigger_cooldowns[trigger_id] = current_time + timedelta(seconds=threshold.cooldown_seconds)
                self._action_cooldowns[action] = current_time + timedelta(seconds=self._config.action_cooldown_seconds)

                # Track trigger state
                trigger_state['last_triggered'] = current_time
                self._active_triggers.add(trigger_id)

                return event

            return None

        except Exception as e:
            self._logger.error(f"Error evaluating trigger {trigger_id}: {e}")
            return None

    def _extract_metric_value(self, trigger_type: TriggerType, metric_name: str,
                             metrics: ResourceMetrics) -> Optional[float]:
        """Extract the relevant metric value from resource metrics."""
        try:
            if trigger_type == TriggerType.MEMORY_PRESSURE:
                if hasattr(metrics, 'memory') and isinstance(metrics.memory, MemoryMetrics):
                    if metric_name == "usage_percent":
                        return metrics.memory.usage_percent
                    elif metric_name == "pressure_score":
                        return metrics.memory.memory_pressure_score
                    elif metric_name == "swap_usage":
                        return metrics.memory.swap_info.usage_percent

            elif trigger_type == TriggerType.GPU_UTILIZATION:
                if hasattr(metrics, 'gpu') and isinstance(metrics.gpu, GPUMetrics):
                    if metric_name == "utilization_percent":
                        return metrics.gpu.utilization_percent
                    elif metric_name == "memory_percent":
                        return metrics.gpu.memory_percent
                    elif metric_name == "temperature":
                        return metrics.gpu.temperature_celsius

            elif trigger_type == TriggerType.THERMAL_THROTTLING:
                if hasattr(metrics, 'thermal') and isinstance(metrics.thermal, ThermalMetrics):
                    if metric_name == "cpu_temperature":
                        return metrics.thermal.cpu_temperature_celsius
                    elif metric_name == "gpu_temperature":
                        return metrics.thermal.gpu_temperature_celsius
                    elif metric_name == "throttling_active":
                        return 1.0 if metrics.thermal.throttling_info.is_throttling else 0.0

            elif trigger_type == TriggerType.DISK_IO_PRESSURE:
                if hasattr(metrics, 'disk') and isinstance(metrics.disk, DiskMetrics):
                    if metric_name == "read_iops":
                        return metrics.disk.io_performance.read_iops
                    elif metric_name == "write_iops":
                        return metrics.disk.io_performance.write_iops
                    elif metric_name == "queue_depth":
                        return metrics.disk.io_performance.queue_depth

            # Generic metric extraction
            if hasattr(metrics, metric_name):
                value = getattr(metrics, metric_name)
                if isinstance(value, (int, float)):
                    return float(value)

            return None

        except Exception as e:
            self._logger.error(f"Error extracting metric {metric_name}: {e}")
            return None

    def _evaluate_condition(self, threshold: MetricThreshold, metric_value: float,
                           trigger_state: Dict[str, Any], current_time: datetime) -> bool:
        """Evaluate if a threshold condition is met."""
        try:
            # Basic comparison conditions
            if threshold.condition == TriggerCondition.GREATER_THAN:
                basic_condition = metric_value > threshold.threshold_value
            elif threshold.condition == TriggerCondition.LESS_THAN:
                basic_condition = metric_value < threshold.threshold_value
            elif threshold.condition == TriggerCondition.EQUALS:
                basic_condition = abs(metric_value - threshold.threshold_value) < 0.001
            elif threshold.condition == TriggerCondition.GREATER_EQUAL:
                basic_condition = metric_value >= threshold.threshold_value
            elif threshold.condition == TriggerCondition.LESS_EQUAL:
                basic_condition = metric_value <= threshold.threshold_value
            else:
                # Trend-based conditions
                return self._evaluate_trend_condition(threshold, metric_value, trigger_state, current_time)

            # Check sustained duration if required
            if threshold.sustained_duration_seconds > 0:
                return self._check_sustained_condition(basic_condition, threshold, trigger_state, current_time)

            return basic_condition

        except Exception as e:
            self._logger.error(f"Error evaluating condition: {e}")
            return False

    def _evaluate_trend_condition(self, threshold: MetricThreshold, metric_value: float,
                                 trigger_state: Dict[str, Any], current_time: datetime) -> bool:
        """Evaluate trend-based conditions."""
        trend_values = trigger_state['trend_values']

        if len(trend_values) < 3:
            return False

        # Calculate trend
        recent_values = [v[1] for v in list(trend_values)[-5:]]
        if len(recent_values) < 3:
            return False

        # Simple linear trend calculation
        x_values = list(range(len(recent_values)))
        n = len(recent_values)
        sum_x = sum(x_values)
        sum_y = sum(recent_values)
        sum_xy = sum(x * y for x, y in zip(x_values, recent_values))
        sum_x2 = sum(x * x for x in x_values)

        # Calculate slope
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return False

        slope = (n * sum_xy - sum_x * sum_y) / denominator

        if threshold.condition == TriggerCondition.TREND_INCREASING:
            return slope > 0.1  # Positive trend threshold
        elif threshold.condition == TriggerCondition.TREND_DECREASING:
            return slope < -0.1  # Negative trend threshold

        return False

    def _check_sustained_condition(self, condition_met: bool, threshold: MetricThreshold,
                                  trigger_state: Dict[str, Any], current_time: datetime) -> bool:
        """Check if a condition has been sustained for the required duration."""
        if condition_met:
            if trigger_state['sustained_start'] is None:
                trigger_state['sustained_start'] = current_time

            sustained_duration = (current_time - trigger_state['sustained_start']).total_seconds()
            return sustained_duration >= threshold.sustained_duration_seconds
        else:
            trigger_state['sustained_start'] = None
            return False

    def _calculate_severity(self, metric_value: float, threshold: MetricThreshold) -> float:
        """Calculate the severity of a triggered condition."""
        try:
            if threshold.condition in [TriggerCondition.GREATER_THAN, TriggerCondition.GREATER_EQUAL]:
                if threshold.threshold_value == 0:
                    return 1.0
                severity = min(1.0, (metric_value - threshold.threshold_value) / threshold.threshold_value)
            elif threshold.condition in [TriggerCondition.LESS_THAN, TriggerCondition.LESS_EQUAL]:
                if threshold.threshold_value == 0:
                    return 1.0
                severity = min(1.0, (threshold.threshold_value - metric_value) / threshold.threshold_value)
            else:
                severity = 0.5  # Default severity for other conditions

            return max(0.1, severity)  # Minimum severity

        except Exception:
            return 0.5

    async def _execute_action(self, event: TriggerEvent, metrics: ResourceMetrics) -> None:
        """Execute an optimization action."""
        try:
            # Check if we have a handler for this action
            if event.action not in self._action_handlers:
                self._logger.warning(f"No handler registered for action: {event.action.value}")
                return

            # Create optimization context
            context = OptimizationContext(
                current_metrics=metrics,
                historical_metrics=list(self._metrics_history),
                active_triggers=self._active_triggers.copy(),
                recent_actions=list(self._recent_events),
                system_load=self._calculate_system_load(metrics),
                available_resources=self._calculate_available_resources(metrics)
            )

            # Execute the handler
            handler = self._action_handlers[event.action]
            if asyncio.iscoroutinefunction(handler):
                await handler(event, context)
            else:
                handler(event, context)

            # Track the event
            self._recent_events.append(event)

            self._logger.info(f"Executed optimization action: {event.action.value} "
                            f"(severity: {event.severity:.2f})")

        except Exception as e:
            self._logger.error(f"Error executing action {event.action.value}: {e}")

    def _calculate_system_load(self, metrics: ResourceMetrics) -> float:
        """Calculate overall system load score."""
        try:
            load_factors = []

            if hasattr(metrics, 'memory') and metrics.memory:
                load_factors.append(metrics.memory.usage_percent / 100.0)

            if hasattr(metrics, 'gpu') and metrics.gpu:
                load_factors.append(metrics.gpu.utilization_percent / 100.0)

            if hasattr(metrics, 'disk') and metrics.disk:
                # Normalize disk usage to 0-1 scale
                disk_load = min(1.0, metrics.disk.io_performance.queue_depth / 10.0)
                load_factors.append(disk_load)

            return sum(load_factors) / len(load_factors) if load_factors else 0.0

        except Exception:
            return 0.5

    def _calculate_available_resources(self, metrics: ResourceMetrics) -> Dict[str, float]:
        """Calculate available resources as percentages."""
        try:
            resources = {}

            if hasattr(metrics, 'memory') and metrics.memory:
                resources['memory'] = 100.0 - metrics.memory.usage_percent

            if hasattr(metrics, 'gpu') and metrics.gpu:
                resources['gpu_compute'] = 100.0 - metrics.gpu.utilization_percent
                resources['gpu_memory'] = 100.0 - metrics.gpu.memory_percent

            if hasattr(metrics, 'disk') and metrics.disk:
                resources['disk_space'] = 100.0 - metrics.disk.storage_info.usage_percent

            return resources

        except Exception:
            return {}

    def get_trigger_statistics(self) -> Dict[str, Any]:
        """Get statistics about trigger performance and activity."""
        with self._lock:
            avg_evaluation_time = (
                sum(self._evaluation_times) / len(self._evaluation_times)
                if self._evaluation_times else 0.0
            )

            return {
                'total_triggers': len(self._triggers),
                'active_triggers': len(self._active_triggers),
                'recent_events': len(self._recent_events),
                'average_evaluation_time_ms': avg_evaluation_time * 1000,
                'monitoring_active': self._monitoring,
                'metrics_history_size': len(self._metrics_history)
            }
