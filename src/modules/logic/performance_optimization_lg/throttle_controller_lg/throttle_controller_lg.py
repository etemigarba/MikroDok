"""
Module: throttle_controller_lg
Description: Manages rate limiting and prevents system overload through intelligent throttling mechanisms
Phase: 2
Location: /src/modules/logic/performance_optimization_lg/throttle_controller_lg/
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
from typing import Dict, List, Optional, Tuple, Any, Callable, Set
from collections import deque, defaultdict

# Local imports
from src.modules.logic.resource_monitor_lg import (
    ResourceMetrics, 
    MemoryMetrics, 
    GPUMetrics,
    ThermalMetrics
)
from src.modules.logic.logging_infrastructure_lg import get_logger


class ThrottleLevel(Enum):
    """Throttling levels."""
    NONE = "NONE"
    LIGHT = "LIGHT"
    MODERATE = "MODERATE"
    HEAVY = "HEAVY"
    EMERGENCY = "EMERGENCY"


class ThrottleReason(Enum):
    """Reasons for throttling."""
    THERMAL_LIMIT = "THERMAL_LIMIT"
    MEMORY_PRESSURE = "MEMORY_PRESSURE"
    GPU_OVERLOAD = "GPU_OVERLOAD"
    CPU_OVERLOAD = "CPU_OVERLOAD"
    POWER_LIMIT = "POWER_LIMIT"
    USER_REQUEST = "USER_REQUEST"
    SYSTEM_PROTECTION = "SYSTEM_PROTECTION"


class ThrottleTarget(Enum):
    """Throttling targets."""
    TRAINING_OPERATIONS = "TRAINING_OPERATIONS"
    INFERENCE_OPERATIONS = "INFERENCE_OPERATIONS"
    PREPROCESSING = "PREPROCESSING"
    BACKGROUND_TASKS = "BACKGROUND_TASKS"
    ALL_OPERATIONS = "ALL_OPERATIONS"


@dataclass
class ThrottleConfiguration:
    """Throttle configuration settings."""
    thermal_threshold_celsius: float = 80.0
    memory_threshold_percent: float = 85.0
    gpu_threshold_percent: float = 90.0
    cpu_threshold_percent: float = 85.0
    power_threshold_watts: Optional[float] = None
    
    # Throttle rates (0.0 = no throttling, 1.0 = complete throttling)
    light_throttle_rate: float = 0.2
    moderate_throttle_rate: float = 0.5
    heavy_throttle_rate: float = 0.8
    emergency_throttle_rate: float = 0.95
    
    # Timing settings
    throttle_check_interval_seconds: float = 1.0
    throttle_ramp_time_seconds: float = 5.0
    recovery_delay_seconds: float = 10.0
    
    # Adaptive settings
    enable_adaptive_throttling: bool = True
    enable_predictive_throttling: bool = True


@dataclass
class ThrottleState:
    """Current throttling state."""
    level: ThrottleLevel
    rate: float
    reasons: List[ThrottleReason]
    targets: List[ThrottleTarget]
    timestamp: datetime
    duration_seconds: float
    estimated_recovery_time: Optional[datetime] = None


@dataclass
class ThrottleEvent:
    """Throttling event record."""
    timestamp: datetime
    event_type: str  # 'start', 'change', 'end'
    old_level: ThrottleLevel
    new_level: ThrottleLevel
    reason: ThrottleReason
    target: ThrottleTarget
    metrics_snapshot: Optional[ResourceMetrics] = None


class IThrottleController(ABC):
    """Interface for throttle control systems."""
    
    @abstractmethod
    async def evaluate_throttling(self, metrics: ResourceMetrics) -> ThrottleState:
        """Evaluate if throttling is needed based on current metrics."""
        pass
    
    @abstractmethod
    def apply_throttle(self, target: ThrottleTarget, rate: float) -> bool:
        """Apply throttling to a specific target."""
        pass
    
    @abstractmethod
    def remove_throttle(self, target: ThrottleTarget) -> bool:
        """Remove throttling from a specific target."""
        pass
    
    @abstractmethod
    def get_current_throttle_state(self) -> ThrottleState:
        """Get current throttling state."""
        pass


class ThrottleController(IThrottleController):
    """Intelligent throttle controller with adaptive rate limiting."""
    
    def __init__(self, config: ThrottleConfiguration):
        """Initialize the throttle controller."""
        self._config = config
        self._logger = get_logger(__name__)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Current state
        self._current_state = ThrottleState(
            level=ThrottleLevel.NONE,
            rate=0.0,
            reasons=[],
            targets=[],
            timestamp=datetime.now(timezone.utc),
            duration_seconds=0.0
        )
        
        # Throttle tracking
        self._active_throttles: Dict[ThrottleTarget, float] = {}
        self._throttle_history: deque = deque(maxlen=1000)
        self._metrics_history: deque = deque(maxlen=100)
        
        # Monitoring
        self._monitoring_enabled = False
        self._monitoring_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self._throttle_callbacks: List[Callable[[ThrottleEvent], None]] = []
        
        # Performance tracking
        self._throttle_effectiveness: Dict[ThrottleReason, float] = defaultdict(float)
        
        self._logger.info("Throttle controller initialized")
    
    async def start_monitoring(self) -> None:
        """Start throttle monitoring."""
        if self._monitoring_enabled:
            self._logger.warning("Throttle monitoring already running")
            return
        
        self._monitoring_enabled = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._logger.info("Throttle monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop throttle monitoring."""
        if not self._monitoring_enabled:
            return
        
        self._monitoring_enabled = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        self._logger.info("Throttle monitoring stopped")
    
    async def _monitoring_loop(self) -> None:
        """Main throttle monitoring loop."""
        try:
            while self._monitoring_enabled:
                start_time = time.time()
                
                # This would get metrics from resource monitor in real implementation
                # For now, we'll skip automatic evaluation
                
                # Calculate sleep time
                elapsed = time.time() - start_time
                sleep_time = max(0, self._config.throttle_check_interval_seconds - elapsed)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._logger.error(f"Error in throttle monitoring loop: {e}")
    
    async def evaluate_throttling(self, metrics: ResourceMetrics) -> ThrottleState:
        """Evaluate if throttling is needed based on current metrics."""
        try:
            with self._lock:
                # Store metrics for analysis
                self._metrics_history.append(metrics)
                
                # Analyze current conditions
                analysis = self._analyze_throttle_conditions(metrics)
                
                # Determine throttle level
                new_level = self._determine_throttle_level(analysis)
                
                # Update throttle state if needed
                if new_level != self._current_state.level:
                    await self._update_throttle_state(new_level, analysis, metrics)
                
                return self._current_state
                
        except Exception as e:
            self._logger.error(f"Error evaluating throttling: {e}")
            return self._current_state

    def apply_throttle(self, target: ThrottleTarget, rate: float) -> bool:
        """Apply throttling to a specific target."""
        try:
            with self._lock:
                # Validate rate
                rate = max(0.0, min(1.0, rate))

                # Apply throttle
                self._active_throttles[target] = rate

                # Log throttle application
                self._logger.info(f"Applied {rate:.2%} throttle to {target}")

                # Update current state
                self._update_current_state()

                return True

        except Exception as e:
            self._logger.error(f"Error applying throttle: {e}")
            return False

    def remove_throttle(self, target: ThrottleTarget) -> bool:
        """Remove throttling from a specific target."""
        try:
            with self._lock:
                if target in self._active_throttles:
                    del self._active_throttles[target]
                    self._logger.info(f"Removed throttle from {target}")

                    # Update current state
                    self._update_current_state()

                    return True

                return False

        except Exception as e:
            self._logger.error(f"Error removing throttle: {e}")
            return False

    def get_current_throttle_state(self) -> ThrottleState:
        """Get current throttling state."""
        with self._lock:
            return self._current_state

    def _analyze_throttle_conditions(self, metrics: ResourceMetrics) -> Dict[str, Any]:
        """Analyze conditions that might require throttling."""
        analysis = {
            'thermal_pressure': 0.0,
            'memory_pressure': 0.0,
            'gpu_pressure': 0.0,
            'cpu_pressure': 0.0,
            'power_pressure': 0.0,
            'reasons': [],
            'severity': 0.0
        }

        try:
            # Thermal analysis
            if metrics.thermal:
                max_temp = max(metrics.thermal.cpu_temperature, metrics.thermal.gpu_temperature)
                thermal_ratio = max_temp / self._config.thermal_threshold_celsius
                analysis['thermal_pressure'] = min(thermal_ratio, 2.0)  # Cap at 2.0

                if thermal_ratio > 1.0:
                    analysis['reasons'].append(ThrottleReason.THERMAL_LIMIT)

            # Memory analysis
            if metrics.memory:
                memory_ratio = metrics.memory.usage_percent / self._config.memory_threshold_percent
                analysis['memory_pressure'] = min(memory_ratio, 2.0)

                if memory_ratio > 1.0:
                    analysis['reasons'].append(ThrottleReason.MEMORY_PRESSURE)

            # GPU analysis
            if metrics.gpu:
                gpu_ratio = metrics.gpu.memory_usage_percent / self._config.gpu_threshold_percent
                analysis['gpu_pressure'] = min(gpu_ratio, 2.0)

                if gpu_ratio > 1.0:
                    analysis['reasons'].append(ThrottleReason.GPU_OVERLOAD)

            # Calculate overall severity
            pressures = [
                analysis['thermal_pressure'],
                analysis['memory_pressure'],
                analysis['gpu_pressure']
            ]
            analysis['severity'] = max(pressures) if pressures else 0.0

        except Exception as e:
            self._logger.error(f"Error analyzing throttle conditions: {e}")

        return analysis

    def _determine_throttle_level(self, analysis: Dict[str, Any]) -> ThrottleLevel:
        """Determine appropriate throttle level based on analysis."""
        try:
            severity = analysis.get('severity', 0.0)

            if severity >= 1.8:
                return ThrottleLevel.EMERGENCY
            elif severity >= 1.4:
                return ThrottleLevel.HEAVY
            elif severity >= 1.2:
                return ThrottleLevel.MODERATE
            elif severity >= 1.0:
                return ThrottleLevel.LIGHT
            else:
                return ThrottleLevel.NONE

        except Exception as e:
            self._logger.error(f"Error determining throttle level: {e}")
            return ThrottleLevel.NONE

    async def _update_throttle_state(self, new_level: ThrottleLevel,
                                   analysis: Dict[str, Any],
                                   metrics: ResourceMetrics) -> None:
        """Update throttle state and apply changes."""
        try:
            old_level = self._current_state.level

            # Determine throttle rate
            throttle_rate = self._get_throttle_rate(new_level)

            # Determine targets
            targets = self._determine_throttle_targets(analysis, new_level)

            # Create new state
            new_state = ThrottleState(
                level=new_level,
                rate=throttle_rate,
                reasons=analysis.get('reasons', []),
                targets=targets,
                timestamp=datetime.now(timezone.utc),
                duration_seconds=0.0
            )

            # Apply throttling changes
            await self._apply_throttle_changes(old_level, new_level, targets, throttle_rate)

            # Update current state
            self._current_state = new_state

            # Record event
            event = ThrottleEvent(
                timestamp=datetime.now(timezone.utc),
                event_type='change' if old_level != ThrottleLevel.NONE else 'start',
                old_level=old_level,
                new_level=new_level,
                reason=analysis.get('reasons', [ThrottleReason.SYSTEM_PROTECTION])[0],
                target=targets[0] if targets else ThrottleTarget.ALL_OPERATIONS,
                metrics_snapshot=metrics
            )

            self._throttle_history.append(event)

            # Notify callbacks
            for callback in self._throttle_callbacks:
                try:
                    callback(event)
                except Exception as e:
                    self._logger.error(f"Error in throttle callback: {e}")

            self._logger.info(f"Throttle state changed: {old_level} -> {new_level} (rate: {throttle_rate:.2%})")

        except Exception as e:
            self._logger.error(f"Error updating throttle state: {e}")

    def _get_throttle_rate(self, level: ThrottleLevel) -> float:
        """Get throttle rate for a given level."""
        rate_map = {
            ThrottleLevel.NONE: 0.0,
            ThrottleLevel.LIGHT: self._config.light_throttle_rate,
            ThrottleLevel.MODERATE: self._config.moderate_throttle_rate,
            ThrottleLevel.HEAVY: self._config.heavy_throttle_rate,
            ThrottleLevel.EMERGENCY: self._config.emergency_throttle_rate
        }
        return rate_map.get(level, 0.0)

    def _determine_throttle_targets(self, analysis: Dict[str, Any],
                                  level: ThrottleLevel) -> List[ThrottleTarget]:
        """Determine which targets should be throttled."""
        targets = []
        reasons = analysis.get('reasons', [])

        try:
            if level == ThrottleLevel.EMERGENCY:
                targets.append(ThrottleTarget.ALL_OPERATIONS)

            elif level == ThrottleLevel.HEAVY:
                targets.extend([
                    ThrottleTarget.TRAINING_OPERATIONS,
                    ThrottleTarget.BACKGROUND_TASKS
                ])

            elif level == ThrottleLevel.MODERATE:
                if ThrottleReason.THERMAL_LIMIT in reasons:
                    targets.append(ThrottleTarget.TRAINING_OPERATIONS)
                if ThrottleReason.GPU_OVERLOAD in reasons:
                    targets.append(ThrottleTarget.INFERENCE_OPERATIONS)
                if ThrottleReason.MEMORY_PRESSURE in reasons:
                    targets.append(ThrottleTarget.BACKGROUND_TASKS)

            elif level == ThrottleLevel.LIGHT:
                targets.append(ThrottleTarget.BACKGROUND_TASKS)

            # Ensure we have at least one target if throttling is needed
            if level != ThrottleLevel.NONE and not targets:
                targets.append(ThrottleTarget.BACKGROUND_TASKS)

        except Exception as e:
            self._logger.error(f"Error determining throttle targets: {e}")

        return targets

    async def _apply_throttle_changes(self, old_level: ThrottleLevel,
                                    new_level: ThrottleLevel,
                                    targets: List[ThrottleTarget],
                                    rate: float) -> None:
        """Apply throttle changes to targets."""
        try:
            if new_level == ThrottleLevel.NONE:
                # Remove all throttles
                for target in list(self._active_throttles.keys()):
                    self.remove_throttle(target)
            else:
                # Apply throttles to targets
                for target in targets:
                    self.apply_throttle(target, rate)

        except Exception as e:
            self._logger.error(f"Error applying throttle changes: {e}")

    def _update_current_state(self) -> None:
        """Update current state based on active throttles."""
        try:
            if not self._active_throttles:
                self._current_state.level = ThrottleLevel.NONE
                self._current_state.rate = 0.0
                self._current_state.targets = []
            else:
                # Determine overall level from active throttles
                max_rate = max(self._active_throttles.values())

                if max_rate >= self._config.emergency_throttle_rate:
                    self._current_state.level = ThrottleLevel.EMERGENCY
                elif max_rate >= self._config.heavy_throttle_rate:
                    self._current_state.level = ThrottleLevel.HEAVY
                elif max_rate >= self._config.moderate_throttle_rate:
                    self._current_state.level = ThrottleLevel.MODERATE
                elif max_rate >= self._config.light_throttle_rate:
                    self._current_state.level = ThrottleLevel.LIGHT
                else:
                    self._current_state.level = ThrottleLevel.NONE

                self._current_state.rate = max_rate
                self._current_state.targets = list(self._active_throttles.keys())

            # Update duration
            now = datetime.now(timezone.utc)
            duration = (now - self._current_state.timestamp).total_seconds()
            self._current_state.duration_seconds = duration

        except Exception as e:
            self._logger.error(f"Error updating current state: {e}")

    def get_throttle_history(self) -> List[ThrottleEvent]:
        """Get throttle event history."""
        with self._lock:
            return list(self._throttle_history)

    def get_active_throttles(self) -> Dict[ThrottleTarget, float]:
        """Get currently active throttles."""
        with self._lock:
            return self._active_throttles.copy()

    def get_throttle_effectiveness(self) -> Dict[ThrottleReason, float]:
        """Get throttle effectiveness metrics."""
        with self._lock:
            return self._throttle_effectiveness.copy()

    def add_throttle_callback(self, callback: Callable[[ThrottleEvent], None]) -> None:
        """Add throttle event callback."""
        self._throttle_callbacks.append(callback)

    def configure_thresholds(self, config: ThrottleConfiguration) -> None:
        """Update throttle configuration."""
        with self._lock:
            self._config = config
            self._logger.info("Throttle configuration updated")

    def force_throttle(self, target: ThrottleTarget, rate: float,
                      reason: ThrottleReason = ThrottleReason.USER_REQUEST) -> bool:
        """Force throttling on a target."""
        try:
            success = self.apply_throttle(target, rate)
            if success:
                # Record as user-requested throttle
                event = ThrottleEvent(
                    timestamp=datetime.now(timezone.utc),
                    event_type='start',
                    old_level=self._current_state.level,
                    new_level=self._current_state.level,
                    reason=reason,
                    target=target
                )
                self._throttle_history.append(event)

                self._logger.info(f"Forced throttle applied: {target} at {rate:.2%}")

            return success

        except Exception as e:
            self._logger.error(f"Error forcing throttle: {e}")
            return False

    def emergency_stop(self) -> bool:
        """Emergency stop all operations."""
        try:
            success = self.apply_throttle(ThrottleTarget.ALL_OPERATIONS, 1.0)
            if success:
                self._logger.warning("Emergency stop activated - all operations throttled")
            return success

        except Exception as e:
            self._logger.error(f"Error in emergency stop: {e}")
            return False
