"""
Module: memory_monitor_lg
Description: Tracks system RAM, swap usage, and memory allocation patterns for both training and inference operations
Phase: 2
Location: /src/modules/logic/resource_monitor_lg/memory_monitor_lg/
"""

# Standard library imports
import asyncio
import gc
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import psutil

# Local imports
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import ValidationEngine


class MemoryType(Enum):
    """Types of memory being monitored."""
    SYSTEM_RAM = "SYSTEM_RAM"
    VIRTUAL_MEMORY = "VIRTUAL_MEMORY"
    SWAP = "SWAP"
    PROCESS_MEMORY = "PROCESS_MEMORY"
    GPU_MEMORY = "GPU_MEMORY"


class AllocationPattern(Enum):
    """Memory allocation patterns."""
    STEADY = "STEADY"
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    VOLATILE = "VOLATILE"
    SPIKE = "SPIKE"
    LEAK_SUSPECTED = "LEAK_SUSPECTED"


@dataclass
class MemoryAllocationPattern:
    """Memory allocation pattern analysis."""
    pattern_type: AllocationPattern
    confidence: float  # 0.0 to 1.0
    trend_slope: float  # MB per second
    volatility_score: float  # Standard deviation
    analysis_window_minutes: int
    detected_at: datetime
    description: str


@dataclass
class SwapUsageInfo:
    """Detailed swap usage information."""
    total_mb: int
    used_mb: int
    free_mb: int
    usage_percent: float
    swap_in_rate_mb_per_sec: float
    swap_out_rate_mb_per_sec: float
    swap_devices: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ProcessMemoryInfo:
    """Process-specific memory information."""
    pid: int
    name: str
    memory_rss_mb: float  # Resident Set Size
    memory_vms_mb: float  # Virtual Memory Size
    memory_percent: float
    memory_shared_mb: float
    memory_private_mb: float
    page_faults: int
    memory_maps_count: int


@dataclass
class MemoryMetrics:
    """Comprehensive memory metrics."""
    timestamp: datetime
    
    # System memory
    total_ram_mb: int
    available_ram_mb: int
    used_ram_mb: int
    free_ram_mb: int
    cached_mb: int
    buffers_mb: int
    usage_percent: float
    
    # Virtual memory
    virtual_total_mb: int
    virtual_available_mb: int
    virtual_used_mb: int
    virtual_percent: float
    
    # Swap information
    swap_info: SwapUsageInfo
    
    # Process memory (current process)
    process_memory: ProcessMemoryInfo
    
    # Memory pressure indicators
    memory_pressure_score: float  # 0.0 to 1.0
    allocation_rate_mb_per_sec: float
    deallocation_rate_mb_per_sec: float
    
    # Garbage collection stats
    gc_collections: Dict[int, int] = field(default_factory=dict)
    gc_collected_objects: int = 0
    gc_uncollectable_objects: int = 0


class MemoryMonitor:
    """Advanced memory monitoring with allocation pattern analysis."""
    
    def __init__(self, app_state_manager: Optional[AppStateManager] = None):
        """Initialize the memory monitor."""
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("memory_monitor")
        self._validation_engine = ValidationEngine()
        
        # Monitoring state
        self._lock = threading.RLock()
        self._monitoring_enabled = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._sampling_interval = 1.0
        self._history_retention_minutes = 60
        
        # Metrics storage
        self._metrics_history: List[MemoryMetrics] = []
        self._current_metrics: Optional[MemoryMetrics] = None
        
        # Pattern analysis
        self._allocation_patterns: List[MemoryAllocationPattern] = []
        self._pattern_analysis_window = 300  # 5 minutes
        
        # Performance tracking
        self._last_swap_stats = None
        self._last_measurement_time = None
        self._process = psutil.Process()
        
        # Memory thresholds
        self._warning_threshold = 85.0  # Percent
        self._critical_threshold = 95.0  # Percent
        self._leak_detection_enabled = True
        
        self._logger.info("Memory monitor initialized")
    
    async def start_monitoring(self, sampling_interval: float = 1.0) -> None:
        """Start memory monitoring."""
        with self._lock:
            if self._monitoring_enabled:
                self._logger.warning("Memory monitoring already started")
                return
            
            self._sampling_interval = sampling_interval
            self._monitoring_enabled = True
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            self._logger.info("Memory monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop memory monitoring."""
        with self._lock:
            if not self._monitoring_enabled:
                return
            
            self._monitoring_enabled = False
            
            if self._monitoring_task:
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
                self._monitoring_task = None
            
            self._logger.info("Memory monitoring stopped")
    
    async def _monitoring_loop(self) -> None:
        """Main memory monitoring loop."""
        try:
            while self._monitoring_enabled:
                start_time = time.time()
                
                # Collect metrics
                metrics = self._collect_memory_metrics()
                
                with self._lock:
                    self._current_metrics = metrics
                    self._metrics_history.append(metrics)
                    
                    # Cleanup old metrics
                    cutoff_time = datetime.now(timezone.utc) - timedelta(
                        minutes=self._history_retention_minutes
                    )
                    self._metrics_history = [
                        m for m in self._metrics_history if m.timestamp >= cutoff_time
                    ]
                    
                    # Analyze allocation patterns
                    if len(self._metrics_history) >= 10:  # Need some history
                        self._analyze_allocation_patterns()
                
                # Calculate sleep time
                elapsed = time.time() - start_time
                sleep_time = max(0, self._sampling_interval - elapsed)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                
        except asyncio.CancelledError:
            self._logger.info("Memory monitoring loop cancelled")
            raise
        except Exception as e:
            self._logger.error(f"Error in memory monitoring loop: {str(e)}")
            raise
    
    def _collect_memory_metrics(self) -> MemoryMetrics:
        """Collect comprehensive memory metrics."""
        try:
            current_time = datetime.now(timezone.utc)
            
            # System memory
            memory = psutil.virtual_memory()
            
            # Swap information
            swap = psutil.swap_memory()
            swap_in_rate = 0.0
            swap_out_rate = 0.0
            
            # Calculate swap rates
            if self._last_swap_stats and self._last_measurement_time:
                time_delta = (current_time - self._last_measurement_time).total_seconds()
                if time_delta > 0:
                    swap_in_delta = swap.sin - self._last_swap_stats.sin
                    swap_out_delta = swap.sout - self._last_swap_stats.sout
                    swap_in_rate = (swap_in_delta / time_delta) / (1024 * 1024)  # MB/s
                    swap_out_rate = (swap_out_delta / time_delta) / (1024 * 1024)  # MB/s
            
            self._last_swap_stats = swap
            
            swap_info = SwapUsageInfo(
                total_mb=swap.total // (1024 * 1024),
                used_mb=swap.used // (1024 * 1024),
                free_mb=swap.free // (1024 * 1024),
                usage_percent=swap.percent,
                swap_in_rate_mb_per_sec=swap_in_rate,
                swap_out_rate_mb_per_sec=swap_out_rate
            )
            
            # Process memory information
            process_memory_info = self._process.memory_info()
            process_memory_full = self._process.memory_full_info()
            
            process_memory = ProcessMemoryInfo(
                pid=self._process.pid,
                name=self._process.name(),
                memory_rss_mb=process_memory_info.rss / (1024 * 1024),
                memory_vms_mb=process_memory_info.vms / (1024 * 1024),
                memory_percent=self._process.memory_percent(),
                memory_shared_mb=getattr(process_memory_full, 'shared', 0) / (1024 * 1024),
                memory_private_mb=getattr(process_memory_full, 'private', 0) / (1024 * 1024),
                page_faults=getattr(process_memory_full, 'pfaults', 0),
                memory_maps_count=len(self._process.memory_maps()) if hasattr(self._process, 'memory_maps') else 0
            )
            
            # Calculate allocation rates
            allocation_rate = 0.0
            deallocation_rate = 0.0
            
            if self._current_metrics and self._last_measurement_time:
                time_delta = (current_time - self._last_measurement_time).total_seconds()
                if time_delta > 0:
                    memory_delta = (memory.used - (self._current_metrics.used_ram_mb * 1024 * 1024)) / (1024 * 1024)
                    if memory_delta > 0:
                        allocation_rate = memory_delta / time_delta
                    else:
                        deallocation_rate = abs(memory_delta) / time_delta
            
            # Memory pressure score (0.0 to 1.0)
            pressure_factors = [
                memory.percent / 100.0,  # RAM usage
                swap.percent / 100.0 if swap.total > 0 else 0.0,  # Swap usage
                min(1.0, (swap_in_rate + swap_out_rate) / 100.0),  # Swap activity
                min(1.0, allocation_rate / 1000.0)  # Allocation rate
            ]
            memory_pressure_score = sum(pressure_factors) / len(pressure_factors)
            
            # Garbage collection stats
            gc_stats = gc.get_stats()
            gc_collections = {i: stat['collections'] for i, stat in enumerate(gc_stats)}
            
            self._last_measurement_time = current_time
            
            return MemoryMetrics(
                timestamp=current_time,
                total_ram_mb=memory.total // (1024 * 1024),
                available_ram_mb=memory.available // (1024 * 1024),
                used_ram_mb=memory.used // (1024 * 1024),
                free_ram_mb=memory.free // (1024 * 1024),
                cached_mb=getattr(memory, 'cached', 0) // (1024 * 1024),
                buffers_mb=getattr(memory, 'buffers', 0) // (1024 * 1024),
                usage_percent=memory.percent,
                virtual_total_mb=(memory.total + swap.total) // (1024 * 1024),
                virtual_available_mb=(memory.available + swap.free) // (1024 * 1024),
                virtual_used_mb=(memory.used + swap.used) // (1024 * 1024),
                virtual_percent=((memory.used + swap.used) / (memory.total + swap.total)) * 100 if (memory.total + swap.total) > 0 else 0,
                swap_info=swap_info,
                process_memory=process_memory,
                memory_pressure_score=memory_pressure_score,
                allocation_rate_mb_per_sec=allocation_rate,
                deallocation_rate_mb_per_sec=deallocation_rate,
                gc_collections=gc_collections,
                gc_collected_objects=gc.get_count()[0],
                gc_uncollectable_objects=len(gc.garbage)
            )
            
        except Exception as e:
            self._logger.error(f"Error collecting memory metrics: {str(e)}")
            # Return default metrics on error
            return MemoryMetrics(
                timestamp=datetime.now(timezone.utc),
                total_ram_mb=8192,
                available_ram_mb=4096,
                used_ram_mb=4096,
                free_ram_mb=4096,
                cached_mb=0,
                buffers_mb=0,
                usage_percent=50.0,
                virtual_total_mb=8192,
                virtual_available_mb=4096,
                virtual_used_mb=4096,
                virtual_percent=50.0,
                swap_info=SwapUsageInfo(0, 0, 0, 0.0, 0.0, 0.0),
                process_memory=ProcessMemoryInfo(0, "unknown", 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0),
                memory_pressure_score=0.5,
                allocation_rate_mb_per_sec=0.0,
                deallocation_rate_mb_per_sec=0.0
            )

    def _analyze_allocation_patterns(self) -> None:
        """Analyze memory allocation patterns for leak detection and optimization."""
        try:
            if len(self._metrics_history) < 10:
                return

            # Get recent metrics for analysis
            analysis_window_minutes = min(self._pattern_analysis_window // 60,
                                        len(self._metrics_history) * self._sampling_interval // 60)

            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=analysis_window_minutes)
            recent_metrics = [m for m in self._metrics_history if m.timestamp >= cutoff_time]

            if len(recent_metrics) < 5:
                return

            # Extract memory usage values
            memory_values = [m.used_ram_mb for m in recent_metrics]
            timestamps = [(m.timestamp - recent_metrics[0].timestamp).total_seconds() for m in recent_metrics]

            # Calculate trend
            if len(memory_values) >= 2:
                # Simple linear regression for trend
                n = len(memory_values)
                sum_x = sum(timestamps)
                sum_y = sum(memory_values)
                sum_xy = sum(x * y for x, y in zip(timestamps, memory_values))
                sum_x2 = sum(x * x for x in timestamps)

                if n * sum_x2 - sum_x * sum_x != 0:
                    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
                    trend_slope_mb_per_sec = slope
                else:
                    trend_slope_mb_per_sec = 0.0

                # Calculate volatility (standard deviation)
                mean_memory = sum_y / n
                variance = sum((y - mean_memory) ** 2 for y in memory_values) / n
                volatility_score = variance ** 0.5

                # Determine pattern type
                pattern_type = self._classify_allocation_pattern(
                    trend_slope_mb_per_sec, volatility_score, memory_values
                )

                # Calculate confidence based on data quality
                confidence = min(1.0, len(recent_metrics) / 60.0)  # More data = higher confidence

                # Create pattern description
                description = self._generate_pattern_description(
                    pattern_type, trend_slope_mb_per_sec, volatility_score
                )

                pattern = MemoryAllocationPattern(
                    pattern_type=pattern_type,
                    confidence=confidence,
                    trend_slope=trend_slope_mb_per_sec,
                    volatility_score=volatility_score,
                    analysis_window_minutes=int(analysis_window_minutes),
                    detected_at=datetime.now(timezone.utc),
                    description=description
                )

                # Add to patterns list (keep only recent patterns)
                self._allocation_patterns.append(pattern)

                # Keep only patterns from last hour
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
                self._allocation_patterns = [
                    p for p in self._allocation_patterns if p.detected_at >= cutoff_time
                ]

                # Log significant patterns
                if pattern_type in [AllocationPattern.LEAK_SUSPECTED, AllocationPattern.SPIKE]:
                    self._logger.warning(f"Memory pattern detected: {description}")
                elif pattern_type != AllocationPattern.STEADY:
                    self._logger.info(f"Memory pattern detected: {description}")

        except Exception as e:
            self._logger.error(f"Error analyzing allocation patterns: {str(e)}")

    def _classify_allocation_pattern(self, slope: float, volatility: float,
                                   memory_values: List[float]) -> AllocationPattern:
        """Classify the memory allocation pattern."""
        # Thresholds for pattern classification
        steady_slope_threshold = 0.1  # MB/sec
        increasing_slope_threshold = 1.0  # MB/sec
        high_volatility_threshold = 100.0  # MB
        spike_threshold = 500.0  # MB sudden change

        # Check for spikes (sudden large changes)
        if len(memory_values) >= 2:
            max_change = max(abs(memory_values[i] - memory_values[i-1])
                           for i in range(1, len(memory_values)))
            if max_change > spike_threshold:
                return AllocationPattern.SPIKE

        # Check for suspected memory leak
        if slope > increasing_slope_threshold and volatility < high_volatility_threshold:
            # Consistent upward trend might indicate a leak
            return AllocationPattern.LEAK_SUSPECTED

        # High volatility
        if volatility > high_volatility_threshold:
            return AllocationPattern.VOLATILE

        # Steady increase
        if slope > steady_slope_threshold:
            return AllocationPattern.INCREASING

        # Steady decrease
        if slope < -steady_slope_threshold:
            return AllocationPattern.DECREASING

        # Steady state
        return AllocationPattern.STEADY

    def _generate_pattern_description(self, pattern_type: AllocationPattern,
                                    slope: float, volatility: float) -> str:
        """Generate a human-readable description of the allocation pattern."""
        if pattern_type == AllocationPattern.STEADY:
            return f"Memory usage is stable (±{volatility:.1f} MB)"
        elif pattern_type == AllocationPattern.INCREASING:
            return f"Memory usage increasing at {slope:.2f} MB/sec (volatility: {volatility:.1f} MB)"
        elif pattern_type == AllocationPattern.DECREASING:
            return f"Memory usage decreasing at {abs(slope):.2f} MB/sec (volatility: {volatility:.1f} MB)"
        elif pattern_type == AllocationPattern.VOLATILE:
            return f"Memory usage is highly volatile (±{volatility:.1f} MB)"
        elif pattern_type == AllocationPattern.SPIKE:
            return f"Memory usage spike detected (volatility: {volatility:.1f} MB)"
        elif pattern_type == AllocationPattern.LEAK_SUSPECTED:
            return f"Potential memory leak detected: consistent increase of {slope:.2f} MB/sec"
        else:
            return f"Unknown pattern (slope: {slope:.2f}, volatility: {volatility:.1f})"

    def get_current_metrics(self) -> Optional[MemoryMetrics]:
        """Get the most recent memory metrics."""
        with self._lock:
            if self._current_metrics is None:
                return self._collect_memory_metrics()
            return self._current_metrics

    def get_metrics_history(self, minutes: int = 5) -> List[MemoryMetrics]:
        """Get historical memory metrics."""
        with self._lock:
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            return [m for m in self._metrics_history if m.timestamp >= cutoff_time]

    def get_allocation_patterns(self, hours: int = 1) -> List[MemoryAllocationPattern]:
        """Get detected allocation patterns."""
        with self._lock:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            return [p for p in self._allocation_patterns if p.detected_at >= cutoff_time]

    def get_memory_summary(self) -> Dict[str, Any]:
        """Get a comprehensive memory usage summary."""
        with self._lock:
            current = self.get_current_metrics()
            if not current:
                return {"error": "No metrics available"}

            recent_patterns = self.get_allocation_patterns(hours=1)

            return {
                "total_ram_gb": current.total_ram_mb / 1024,
                "available_ram_gb": current.available_ram_mb / 1024,
                "used_ram_gb": current.used_ram_mb / 1024,
                "usage_percent": current.usage_percent,
                "swap_total_gb": current.swap_info.total_mb / 1024,
                "swap_used_gb": current.swap_info.used_mb / 1024,
                "swap_usage_percent": current.swap_info.usage_percent,
                "process_memory_gb": current.process_memory.memory_rss_mb / 1024,
                "process_memory_percent": current.process_memory.memory_percent,
                "memory_pressure_score": current.memory_pressure_score,
                "allocation_rate_mb_per_sec": current.allocation_rate_mb_per_sec,
                "deallocation_rate_mb_per_sec": current.deallocation_rate_mb_per_sec,
                "recent_patterns": [
                    {
                        "type": p.pattern_type.value,
                        "confidence": p.confidence,
                        "description": p.description,
                        "detected_at": p.detected_at.isoformat()
                    }
                    for p in recent_patterns
                ],
                "gc_collections": current.gc_collections,
                "gc_uncollectable_objects": current.gc_uncollectable_objects
            }

    def force_garbage_collection(self) -> Dict[str, int]:
        """Force garbage collection and return statistics."""
        try:
            before_count = sum(gc.get_count())
            collected = gc.collect()
            after_count = sum(gc.get_count())

            self._logger.info(f"Forced garbage collection: {collected} objects collected")

            return {
                "objects_before": before_count,
                "objects_after": after_count,
                "objects_collected": collected,
                "uncollectable_objects": len(gc.garbage)
            }

        except Exception as e:
            self._logger.error(f"Error during garbage collection: {str(e)}")
            return {"error": str(e)}

    def configure_thresholds(self, warning_percent: float = 85.0,
                           critical_percent: float = 95.0) -> None:
        """Configure memory usage thresholds."""
        with self._lock:
            self._warning_threshold = warning_percent
            self._critical_threshold = critical_percent
            self._logger.info(f"Memory thresholds updated: warning={warning_percent}%, critical={critical_percent}%")

    def is_memory_pressure_high(self) -> bool:
        """Check if memory pressure is currently high."""
        current = self.get_current_metrics()
        if not current:
            return False

        return (current.usage_percent > self._warning_threshold or
                current.memory_pressure_score > 0.8)

    def get_memory_recommendations(self) -> List[str]:
        """Get memory optimization recommendations."""
        recommendations = []
        current = self.get_current_metrics()

        if not current:
            return ["Unable to analyze memory - no metrics available"]

        if current.usage_percent > self._critical_threshold:
            recommendations.append("Critical: Memory usage is very high - consider freeing memory or adding more RAM")
        elif current.usage_percent > self._warning_threshold:
            recommendations.append("Warning: Memory usage is high - monitor for potential issues")

        if current.swap_info.usage_percent > 50:
            recommendations.append("High swap usage detected - consider adding more RAM for better performance")

        if current.memory_pressure_score > 0.8:
            recommendations.append("High memory pressure detected - consider optimizing memory usage")

        recent_patterns = self.get_allocation_patterns(hours=1)
        leak_patterns = [p for p in recent_patterns if p.pattern_type == AllocationPattern.LEAK_SUSPECTED]
        if leak_patterns:
            recommendations.append("Potential memory leak detected - investigate memory allocation patterns")

        if current.gc_uncollectable_objects > 100:
            recommendations.append("High number of uncollectable objects - check for circular references")

        if not recommendations:
            recommendations.append("Memory usage appears normal")

        return recommendations

    def __del__(self):
        """Cleanup on destruction."""
        if self._monitoring_enabled:
            asyncio.create_task(self.stop_monitoring())
