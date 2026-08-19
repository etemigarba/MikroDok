"""
Module: bottleneck_detector_lg
Description: Identifies performance bottlenecks and suggests optimization strategies based on resource utilization patterns
Phase: 2
Location: /src/modules/logic/resource_predictor_lg/bottleneck_detector_lg/
"""

# Standard library imports
import asyncio
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Set
import statistics

# Third-party imports
import numpy as np

# Local imports
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_log_manager
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import ValidationEngine
from src.modules.logic.resource_monitor_lg import (
    ResourceMetrics, 
    GPUMetrics, 
    MemoryMetrics, 
    DiskMetrics, 
    ThermalMetrics
)


class BottleneckType(Enum):
    """Types of performance bottlenecks."""
    CPU_BOUND = "CPU_BOUND"
    MEMORY_BOUND = "MEMORY_BOUND"
    GPU_BOUND = "GPU_BOUND"
    DISK_IO_BOUND = "DISK_IO_BOUND"
    THERMAL_THROTTLING = "THERMAL_THROTTLING"
    NETWORK_BOUND = "NETWORK_BOUND"
    MEMORY_BANDWIDTH = "MEMORY_BANDWIDTH"
    GPU_MEMORY = "GPU_MEMORY"
    CACHE_MISS = "CACHE_MISS"
    SYNCHRONIZATION = "SYNCHRONIZATION"


class BottleneckSeverity(Enum):
    """Severity levels for bottlenecks."""
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class OptimizationStrategy(Enum):
    """Optimization strategies for different bottlenecks."""
    INCREASE_PARALLELISM = "INCREASE_PARALLELISM"
    REDUCE_MEMORY_USAGE = "REDUCE_MEMORY_USAGE"
    OPTIMIZE_DISK_ACCESS = "OPTIMIZE_DISK_ACCESS"
    IMPROVE_THERMAL_MANAGEMENT = "IMPROVE_THERMAL_MANAGEMENT"
    UPGRADE_HARDWARE = "UPGRADE_HARDWARE"
    ADJUST_BATCH_SIZE = "ADJUST_BATCH_SIZE"
    ENABLE_CACHING = "ENABLE_CACHING"
    OPTIMIZE_ALGORITHMS = "OPTIMIZE_ALGORITHMS"
    LOAD_BALANCING = "LOAD_BALANCING"
    MEMORY_POOLING = "MEMORY_POOLING"


@dataclass
class OptimizationRecommendation:
    """Optimization recommendation for addressing bottlenecks."""
    strategy: OptimizationStrategy
    description: str
    expected_improvement: float  # Percentage improvement expected
    implementation_difficulty: str  # "Easy", "Moderate", "Hard"
    estimated_time_hours: float
    prerequisites: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    metrics_to_monitor: List[str] = field(default_factory=list)


@dataclass
class PerformanceBottleneck:
    """Detected performance bottleneck."""
    bottleneck_type: BottleneckType
    severity: BottleneckSeverity
    confidence: float  # 0.0 to 1.0
    affected_resources: List[str]
    detection_timestamp: datetime
    duration_seconds: float
    impact_score: float  # 0.0 to 1.0
    root_cause: str
    symptoms: List[str] = field(default_factory=list)
    related_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class ResourceBottleneck:
    """Resource-specific bottleneck information."""
    resource_name: str
    utilization_percent: float
    threshold_percent: float
    peak_utilization: float
    average_utilization: float
    utilization_trend: str  # "increasing", "decreasing", "stable"
    contention_score: float
    efficiency_score: float


@dataclass
class SystemBottleneck:
    """System-wide bottleneck analysis."""
    primary_bottleneck: PerformanceBottleneck
    secondary_bottlenecks: List[PerformanceBottleneck]
    resource_bottlenecks: List[ResourceBottleneck]
    system_efficiency: float
    recommendations: List[OptimizationRecommendation]
    analysis_timestamp: datetime
    confidence_score: float


@dataclass
class BottleneckConfiguration:
    """Configuration for bottleneck detection."""
    cpu_threshold: float = 80.0
    memory_threshold: float = 85.0
    gpu_threshold: float = 90.0
    disk_io_threshold: float = 75.0
    thermal_threshold: float = 80.0
    analysis_window_minutes: int = 10
    detection_sensitivity: float = 0.7
    min_duration_seconds: float = 30.0
    trend_analysis_points: int = 20
    enable_predictive_detection: bool = True


class IBottleneckDetector(ABC):
    """Interface for bottleneck detection systems."""
    
    @abstractmethod
    async def analyze_bottlenecks(self) -> SystemBottleneck:
        """Analyze current system for bottlenecks."""
        pass
    
    @abstractmethod
    def add_metrics(self, metrics: ResourceMetrics) -> None:
        """Add resource metrics for analysis."""
        pass
    
    @abstractmethod
    def get_recommendations(self, bottleneck_type: BottleneckType) -> List[OptimizationRecommendation]:
        """Get optimization recommendations for a bottleneck type."""
        pass
    
    @abstractmethod
    async def detect_real_time_bottlenecks(self) -> List[PerformanceBottleneck]:
        """Detect bottlenecks in real-time."""
        pass


class BottleneckDetector(IBottleneckDetector):
    """Advanced bottleneck detection and optimization recommendation system."""
    
    def __init__(self, 
                 config: Optional[BottleneckConfiguration] = None,
                 app_state_manager: Optional[AppStateManager] = None):
        """Initialize the bottleneck detector."""
        self._config = config or BottleneckConfiguration()
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("bottleneck_detector")
        self._validation_engine = ValidationEngine()
        
        # Data storage
        self._lock = threading.RLock()
        self._metrics_history: deque = deque(maxlen=1000)  # Store last 1000 metrics
        self._bottleneck_history: List[PerformanceBottleneck] = []
        self._resource_utilization: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Analysis state
        self._last_analysis: Optional[datetime] = None
        self._current_bottlenecks: List[PerformanceBottleneck] = []
        self._trend_data: Dict[str, List[float]] = defaultdict(list)
        
        # Optimization knowledge base
        self._optimization_strategies = self._initialize_optimization_strategies()
        
        self._logger.info("Bottleneck detector initialized")
    
    async def analyze_bottlenecks(self) -> SystemBottleneck:
        """
        Perform comprehensive bottleneck analysis.
        
        Returns:
            Complete system bottleneck analysis
        """
        try:
            analysis_start = time.time()
            
            # Get recent metrics for analysis
            recent_metrics = self._get_recent_metrics()
            if not recent_metrics:
                raise ValueError("Insufficient metrics data for analysis")
            
            # Detect individual bottlenecks
            detected_bottlenecks = await self._detect_bottlenecks(recent_metrics)
            
            # Analyze resource-specific bottlenecks
            resource_bottlenecks = self._analyze_resource_bottlenecks(recent_metrics)
            
            # Determine primary and secondary bottlenecks
            primary_bottleneck = self._identify_primary_bottleneck(detected_bottlenecks)
            secondary_bottlenecks = [b for b in detected_bottlenecks if b != primary_bottleneck]
            
            # Calculate system efficiency
            system_efficiency = self._calculate_system_efficiency(recent_metrics)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(detected_bottlenecks)
            
            # Calculate overall confidence
            confidence_score = self._calculate_analysis_confidence(detected_bottlenecks)
            
            analysis_time = time.time() - analysis_start
            
            system_bottleneck = SystemBottleneck(
                primary_bottleneck=primary_bottleneck,
                secondary_bottlenecks=secondary_bottlenecks,
                resource_bottlenecks=resource_bottlenecks,
                system_efficiency=system_efficiency,
                recommendations=recommendations,
                analysis_timestamp=datetime.now(timezone.utc),
                confidence_score=confidence_score
            )
            
            # Update analysis state
            with self._lock:
                self._last_analysis = datetime.now(timezone.utc)
                self._current_bottlenecks = detected_bottlenecks
            
            self._logger.info(f"Bottleneck analysis completed in {analysis_time:.3f}s, "
                            f"found {len(detected_bottlenecks)} bottlenecks")
            
            return system_bottleneck
            
        except Exception as e:
            self._logger.error(f"Error during bottleneck analysis: {e}")
            raise
    
    def add_metrics(self, metrics: ResourceMetrics) -> None:
        """
        Add resource metrics for bottleneck analysis.
        
        Args:
            metrics: Resource metrics to analyze
        """
        try:
            with self._lock:
                # Store complete metrics
                self._metrics_history.append(metrics)
                
                # Store individual resource utilization
                self._resource_utilization['cpu'].append(metrics.cpu_usage_percent)
                self._resource_utilization['memory'].append(metrics.memory_usage_percent)
                
                # Add GPU metrics if available
                if hasattr(metrics, 'gpu_usage_percent'):
                    self._resource_utilization['gpu'].append(metrics.gpu_usage_percent)
                
                # Add disk metrics if available
                if hasattr(metrics, 'disk_usage_percent'):
                    self._resource_utilization['disk'].append(metrics.disk_usage_percent)
                
                # Add thermal metrics if available
                if hasattr(metrics, 'temperature_celsius'):
                    self._resource_utilization['thermal'].append(metrics.temperature_celsius)
                
                # Update trend data
                self._update_trend_data(metrics)
            
            # Trigger real-time detection if enabled
            if self._config.enable_predictive_detection:
                asyncio.create_task(self._check_real_time_bottlenecks())
                
        except Exception as e:
            self._logger.error(f"Error adding metrics: {e}")
    
    def get_recommendations(self, bottleneck_type: BottleneckType) -> List[OptimizationRecommendation]:
        """
        Get optimization recommendations for a specific bottleneck type.
        
        Args:
            bottleneck_type: Type of bottleneck to get recommendations for
            
        Returns:
            List of optimization recommendations
        """
        return self._optimization_strategies.get(bottleneck_type, [])
    
    async def detect_real_time_bottlenecks(self) -> List[PerformanceBottleneck]:
        """
        Detect bottlenecks in real-time based on current metrics.
        
        Returns:
            List of currently detected bottlenecks
        """
        try:
            recent_metrics = self._get_recent_metrics(minutes=2)  # Very recent data
            if not recent_metrics:
                return []
            
            bottlenecks = []
            
            # Quick CPU bottleneck check
            cpu_bottleneck = self._detect_cpu_bottleneck(recent_metrics)
            if cpu_bottleneck:
                bottlenecks.append(cpu_bottleneck)
            
            # Quick memory bottleneck check
            memory_bottleneck = self._detect_memory_bottleneck(recent_metrics)
            if memory_bottleneck:
                bottlenecks.append(memory_bottleneck)
            
            # Quick GPU bottleneck check
            gpu_bottleneck = self._detect_gpu_bottleneck(recent_metrics)
            if gpu_bottleneck:
                bottlenecks.append(gpu_bottleneck)
            
            # Quick thermal bottleneck check
            thermal_bottleneck = self._detect_thermal_bottleneck(recent_metrics)
            if thermal_bottleneck:
                bottlenecks.append(thermal_bottleneck)
            
            return bottlenecks
            
        except Exception as e:
            self._logger.error(f"Error in real-time bottleneck detection: {e}")
            return []

    def _get_recent_metrics(self, minutes: int = 10) -> List[ResourceMetrics]:
        """Get recent metrics within the specified time window."""
        with self._lock:
            if not self._metrics_history:
                return []

            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            return [m for m in self._metrics_history if m.timestamp >= cutoff_time]

    async def _detect_bottlenecks(self, metrics: List[ResourceMetrics]) -> List[PerformanceBottleneck]:
        """Detect all types of bottlenecks from metrics."""
        bottlenecks = []

        # CPU bottleneck detection
        cpu_bottleneck = self._detect_cpu_bottleneck(metrics)
        if cpu_bottleneck:
            bottlenecks.append(cpu_bottleneck)

        # Memory bottleneck detection
        memory_bottleneck = self._detect_memory_bottleneck(metrics)
        if memory_bottleneck:
            bottlenecks.append(memory_bottleneck)

        # GPU bottleneck detection
        gpu_bottleneck = self._detect_gpu_bottleneck(metrics)
        if gpu_bottleneck:
            bottlenecks.append(gpu_bottleneck)

        # Disk I/O bottleneck detection
        disk_bottleneck = self._detect_disk_bottleneck(metrics)
        if disk_bottleneck:
            bottlenecks.append(disk_bottleneck)

        # Thermal bottleneck detection
        thermal_bottleneck = self._detect_thermal_bottleneck(metrics)
        if thermal_bottleneck:
            bottlenecks.append(thermal_bottleneck)

        # Memory bandwidth bottleneck detection
        bandwidth_bottleneck = self._detect_memory_bandwidth_bottleneck(metrics)
        if bandwidth_bottleneck:
            bottlenecks.append(bandwidth_bottleneck)

        return bottlenecks

    def _detect_cpu_bottleneck(self, metrics: List[ResourceMetrics]) -> Optional[PerformanceBottleneck]:
        """Detect CPU bottlenecks."""
        if not metrics:
            return None

        cpu_usage = [m.cpu_usage_percent for m in metrics]
        avg_usage = statistics.mean(cpu_usage)
        max_usage = max(cpu_usage)

        # Check if CPU usage exceeds threshold
        if avg_usage > self._config.cpu_threshold:
            # Calculate severity
            if avg_usage > 95:
                severity = BottleneckSeverity.CRITICAL
            elif avg_usage > 90:
                severity = BottleneckSeverity.HIGH
            elif avg_usage > 85:
                severity = BottleneckSeverity.MODERATE
            else:
                severity = BottleneckSeverity.LOW

            # Calculate confidence based on consistency
            consistency = 1.0 - (statistics.stdev(cpu_usage) / (avg_usage + 1e-8))
            confidence = min(1.0, max(0.5, consistency))

            # Calculate duration
            duration = (metrics[-1].timestamp - metrics[0].timestamp).total_seconds()

            # Calculate impact score
            impact_score = min(1.0, (avg_usage - self._config.cpu_threshold) / (100 - self._config.cpu_threshold))

            return PerformanceBottleneck(
                bottleneck_type=BottleneckType.CPU_BOUND,
                severity=severity,
                confidence=confidence,
                affected_resources=['CPU'],
                detection_timestamp=datetime.now(timezone.utc),
                duration_seconds=duration,
                impact_score=impact_score,
                root_cause=f"CPU utilization averaging {avg_usage:.1f}% exceeds threshold of {self._config.cpu_threshold}%",
                symptoms=[
                    f"High CPU usage: {avg_usage:.1f}%",
                    f"Peak CPU usage: {max_usage:.1f}%",
                    "Potential thread contention or compute-intensive operations"
                ],
                related_metrics={
                    'average_cpu_usage': avg_usage,
                    'peak_cpu_usage': max_usage,
                    'cpu_threshold': self._config.cpu_threshold
                }
            )

        return None

    def _detect_memory_bottleneck(self, metrics: List[ResourceMetrics]) -> Optional[PerformanceBottleneck]:
        """Detect memory bottlenecks."""
        if not metrics:
            return None

        memory_usage = [m.memory_usage_percent for m in metrics]
        avg_usage = statistics.mean(memory_usage)
        max_usage = max(memory_usage)

        # Check if memory usage exceeds threshold
        if avg_usage > self._config.memory_threshold:
            # Calculate severity
            if avg_usage > 95:
                severity = BottleneckSeverity.CRITICAL
            elif avg_usage > 90:
                severity = BottleneckSeverity.HIGH
            elif avg_usage > 87:
                severity = BottleneckSeverity.MODERATE
            else:
                severity = BottleneckSeverity.LOW

            # Calculate confidence
            consistency = 1.0 - (statistics.stdev(memory_usage) / (avg_usage + 1e-8))
            confidence = min(1.0, max(0.5, consistency))

            # Calculate duration
            duration = (metrics[-1].timestamp - metrics[0].timestamp).total_seconds()

            # Calculate impact score
            impact_score = min(1.0, (avg_usage - self._config.memory_threshold) / (100 - self._config.memory_threshold))

            # Check for memory pressure indicators
            symptoms = [
                f"High memory usage: {avg_usage:.1f}%",
                f"Peak memory usage: {max_usage:.1f}%"
            ]

            # Check for swap usage if available
            swap_usage = []
            for m in metrics:
                if hasattr(m, 'swap_usage_percent'):
                    swap_usage.append(m.swap_usage_percent)

            if swap_usage and statistics.mean(swap_usage) > 10:
                symptoms.append(f"High swap usage: {statistics.mean(swap_usage):.1f}%")
                severity = BottleneckSeverity.HIGH  # Upgrade severity if swapping

            return PerformanceBottleneck(
                bottleneck_type=BottleneckType.MEMORY_BOUND,
                severity=severity,
                confidence=confidence,
                affected_resources=['RAM', 'Swap'],
                detection_timestamp=datetime.now(timezone.utc),
                duration_seconds=duration,
                impact_score=impact_score,
                root_cause=f"Memory utilization averaging {avg_usage:.1f}% exceeds threshold of {self._config.memory_threshold}%",
                symptoms=symptoms,
                related_metrics={
                    'average_memory_usage': avg_usage,
                    'peak_memory_usage': max_usage,
                    'memory_threshold': self._config.memory_threshold,
                    'swap_usage': statistics.mean(swap_usage) if swap_usage else 0
                }
            )

        return None

    def _detect_gpu_bottleneck(self, metrics: List[ResourceMetrics]) -> Optional[PerformanceBottleneck]:
        """Detect GPU bottlenecks."""
        if not metrics:
            return None

        # Extract GPU usage if available
        gpu_usage = []
        gpu_memory_usage = []

        for m in metrics:
            if hasattr(m, 'gpu_usage_percent'):
                gpu_usage.append(m.gpu_usage_percent)
            if hasattr(m, 'gpu_memory_usage_percent'):
                gpu_memory_usage.append(m.gpu_memory_usage_percent)

        if not gpu_usage:
            return None

        avg_usage = statistics.mean(gpu_usage)
        max_usage = max(gpu_usage)

        # Check if GPU usage exceeds threshold
        if avg_usage > self._config.gpu_threshold:
            # Calculate severity
            if avg_usage > 98:
                severity = BottleneckSeverity.CRITICAL
            elif avg_usage > 95:
                severity = BottleneckSeverity.HIGH
            elif avg_usage > 92:
                severity = BottleneckSeverity.MODERATE
            else:
                severity = BottleneckSeverity.LOW

            # Calculate confidence
            consistency = 1.0 - (statistics.stdev(gpu_usage) / (avg_usage + 1e-8))
            confidence = min(1.0, max(0.5, consistency))

            # Calculate duration
            duration = (metrics[-1].timestamp - metrics[0].timestamp).total_seconds()

            # Calculate impact score
            impact_score = min(1.0, (avg_usage - self._config.gpu_threshold) / (100 - self._config.gpu_threshold))

            symptoms = [
                f"High GPU usage: {avg_usage:.1f}%",
                f"Peak GPU usage: {max_usage:.1f}%"
            ]

            # Check GPU memory usage
            if gpu_memory_usage:
                avg_memory = statistics.mean(gpu_memory_usage)
                if avg_memory > 85:
                    symptoms.append(f"High GPU memory usage: {avg_memory:.1f}%")
                    if avg_memory > 95:
                        severity = BottleneckSeverity.CRITICAL

            return PerformanceBottleneck(
                bottleneck_type=BottleneckType.GPU_BOUND,
                severity=severity,
                confidence=confidence,
                affected_resources=['GPU', 'VRAM'],
                detection_timestamp=datetime.now(timezone.utc),
                duration_seconds=duration,
                impact_score=impact_score,
                root_cause=f"GPU utilization averaging {avg_usage:.1f}% exceeds threshold of {self._config.gpu_threshold}%",
                symptoms=symptoms,
                related_metrics={
                    'average_gpu_usage': avg_usage,
                    'peak_gpu_usage': max_usage,
                    'gpu_threshold': self._config.gpu_threshold,
                    'gpu_memory_usage': statistics.mean(gpu_memory_usage) if gpu_memory_usage else 0
                }
            )

        return None

    def _detect_disk_bottleneck(self, metrics: List[ResourceMetrics]) -> Optional[PerformanceBottleneck]:
        """Detect disk I/O bottlenecks."""
        if not metrics:
            return None

        # Extract disk metrics if available
        disk_usage = []
        disk_io_usage = []

        for m in metrics:
            if hasattr(m, 'disk_usage_percent'):
                disk_usage.append(m.disk_usage_percent)
            if hasattr(m, 'disk_io_percent'):
                disk_io_usage.append(m.disk_io_percent)

        if not disk_usage and not disk_io_usage:
            return None

        # Analyze disk space usage
        if disk_usage:
            avg_disk_usage = statistics.mean(disk_usage)
            if avg_disk_usage > 90:  # High disk space usage
                severity = BottleneckSeverity.HIGH if avg_disk_usage > 95 else BottleneckSeverity.MODERATE

                return PerformanceBottleneck(
                    bottleneck_type=BottleneckType.DISK_IO_BOUND,
                    severity=severity,
                    confidence=0.8,
                    affected_resources=['Disk'],
                    detection_timestamp=datetime.now(timezone.utc),
                    duration_seconds=(metrics[-1].timestamp - metrics[0].timestamp).total_seconds(),
                    impact_score=min(1.0, (avg_disk_usage - 85) / 15),
                    root_cause=f"Disk space usage at {avg_disk_usage:.1f}% is critically high",
                    symptoms=[
                        f"High disk usage: {avg_disk_usage:.1f}%",
                        "Risk of disk space exhaustion",
                        "Potential I/O performance degradation"
                    ],
                    related_metrics={'disk_usage': avg_disk_usage}
                )

        # Analyze disk I/O usage
        if disk_io_usage:
            avg_io_usage = statistics.mean(disk_io_usage)
            if avg_io_usage > self._config.disk_io_threshold:
                severity = BottleneckSeverity.HIGH if avg_io_usage > 90 else BottleneckSeverity.MODERATE

                return PerformanceBottleneck(
                    bottleneck_type=BottleneckType.DISK_IO_BOUND,
                    severity=severity,
                    confidence=0.7,
                    affected_resources=['Disk I/O'],
                    detection_timestamp=datetime.now(timezone.utc),
                    duration_seconds=(metrics[-1].timestamp - metrics[0].timestamp).total_seconds(),
                    impact_score=min(1.0, (avg_io_usage - self._config.disk_io_threshold) / (100 - self._config.disk_io_threshold)),
                    root_cause=f"Disk I/O utilization at {avg_io_usage:.1f}% exceeds threshold",
                    symptoms=[
                        f"High disk I/O: {avg_io_usage:.1f}%",
                        "Potential storage bottleneck",
                        "Slow read/write operations"
                    ],
                    related_metrics={'disk_io_usage': avg_io_usage}
                )

        return None

    def _detect_thermal_bottleneck(self, metrics: List[ResourceMetrics]) -> Optional[PerformanceBottleneck]:
        """Detect thermal throttling bottlenecks."""
        if not metrics:
            return None

        # Extract thermal metrics if available
        temperatures = []

        for m in metrics:
            if hasattr(m, 'temperature_celsius'):
                temperatures.append(m.temperature_celsius)

        if not temperatures:
            return None

        avg_temp = statistics.mean(temperatures)
        max_temp = max(temperatures)

        # Check if temperature exceeds threshold
        if avg_temp > self._config.thermal_threshold:
            # Calculate severity based on temperature
            if avg_temp > 90:
                severity = BottleneckSeverity.CRITICAL
            elif avg_temp > 85:
                severity = BottleneckSeverity.HIGH
            elif avg_temp > 82:
                severity = BottleneckSeverity.MODERATE
            else:
                severity = BottleneckSeverity.LOW

            # Calculate confidence
            confidence = min(1.0, (avg_temp - self._config.thermal_threshold) / 20)

            # Calculate duration
            duration = (metrics[-1].timestamp - metrics[0].timestamp).total_seconds()

            # Calculate impact score
            impact_score = min(1.0, (avg_temp - self._config.thermal_threshold) / (100 - self._config.thermal_threshold))

            return PerformanceBottleneck(
                bottleneck_type=BottleneckType.THERMAL_THROTTLING,
                severity=severity,
                confidence=confidence,
                affected_resources=['CPU', 'GPU', 'System'],
                detection_timestamp=datetime.now(timezone.utc),
                duration_seconds=duration,
                impact_score=impact_score,
                root_cause=f"System temperature averaging {avg_temp:.1f}°C exceeds safe threshold",
                symptoms=[
                    f"High temperature: {avg_temp:.1f}°C",
                    f"Peak temperature: {max_temp:.1f}°C",
                    "Risk of thermal throttling",
                    "Potential performance degradation"
                ],
                related_metrics={
                    'average_temperature': avg_temp,
                    'peak_temperature': max_temp,
                    'thermal_threshold': self._config.thermal_threshold
                }
            )

        return None

    def _detect_memory_bandwidth_bottleneck(self, metrics: List[ResourceMetrics]) -> Optional[PerformanceBottleneck]:
        """Detect memory bandwidth bottlenecks."""
        if not metrics or len(metrics) < 5:
            return None

        # Analyze memory usage patterns for bandwidth issues
        memory_usage = [m.memory_usage_percent for m in metrics]

        # Look for rapid memory usage fluctuations (indicator of bandwidth issues)
        usage_changes = [abs(memory_usage[i] - memory_usage[i-1]) for i in range(1, len(memory_usage))]
        avg_change = statistics.mean(usage_changes)

        # High memory usage with frequent changes suggests bandwidth bottleneck
        avg_memory = statistics.mean(memory_usage)

        if avg_memory > 70 and avg_change > 5:  # High usage with high volatility
            severity = BottleneckSeverity.MODERATE
            if avg_memory > 85 and avg_change > 10:
                severity = BottleneckSeverity.HIGH

            confidence = min(1.0, avg_change / 20)  # Confidence based on volatility

            return PerformanceBottleneck(
                bottleneck_type=BottleneckType.MEMORY_BANDWIDTH,
                severity=severity,
                confidence=confidence,
                affected_resources=['Memory Bus', 'RAM'],
                detection_timestamp=datetime.now(timezone.utc),
                duration_seconds=(metrics[-1].timestamp - metrics[0].timestamp).total_seconds(),
                impact_score=min(1.0, avg_change / 15),
                root_cause=f"Memory bandwidth saturation indicated by high usage volatility",
                symptoms=[
                    f"Memory usage volatility: {avg_change:.1f}%",
                    f"Average memory usage: {avg_memory:.1f}%",
                    "Frequent memory allocation/deallocation",
                    "Potential memory bus saturation"
                ],
                related_metrics={
                    'memory_volatility': avg_change,
                    'average_memory_usage': avg_memory
                }
            )

        return None

    def _analyze_resource_bottlenecks(self, metrics: List[ResourceMetrics]) -> List[ResourceBottleneck]:
        """Analyze resource-specific bottlenecks."""
        resource_bottlenecks = []

        if not metrics:
            return resource_bottlenecks

        # Analyze CPU
        cpu_usage = [m.cpu_usage_percent for m in metrics]
        if cpu_usage:
            cpu_bottleneck = ResourceBottleneck(
                resource_name="CPU",
                utilization_percent=statistics.mean(cpu_usage),
                threshold_percent=self._config.cpu_threshold,
                peak_utilization=max(cpu_usage),
                average_utilization=statistics.mean(cpu_usage),
                utilization_trend=self._calculate_trend(cpu_usage),
                contention_score=self._calculate_contention_score(cpu_usage),
                efficiency_score=self._calculate_efficiency_score(cpu_usage)
            )
            resource_bottlenecks.append(cpu_bottleneck)

        # Analyze Memory
        memory_usage = [m.memory_usage_percent for m in metrics]
        if memory_usage:
            memory_bottleneck = ResourceBottleneck(
                resource_name="Memory",
                utilization_percent=statistics.mean(memory_usage),
                threshold_percent=self._config.memory_threshold,
                peak_utilization=max(memory_usage),
                average_utilization=statistics.mean(memory_usage),
                utilization_trend=self._calculate_trend(memory_usage),
                contention_score=self._calculate_contention_score(memory_usage),
                efficiency_score=self._calculate_efficiency_score(memory_usage)
            )
            resource_bottlenecks.append(memory_bottleneck)

        # Analyze GPU if available
        gpu_usage = []
        for m in metrics:
            if hasattr(m, 'gpu_usage_percent'):
                gpu_usage.append(m.gpu_usage_percent)

        if gpu_usage:
            gpu_bottleneck = ResourceBottleneck(
                resource_name="GPU",
                utilization_percent=statistics.mean(gpu_usage),
                threshold_percent=self._config.gpu_threshold,
                peak_utilization=max(gpu_usage),
                average_utilization=statistics.mean(gpu_usage),
                utilization_trend=self._calculate_trend(gpu_usage),
                contention_score=self._calculate_contention_score(gpu_usage),
                efficiency_score=self._calculate_efficiency_score(gpu_usage)
            )
            resource_bottlenecks.append(gpu_bottleneck)

        return resource_bottlenecks

    def _identify_primary_bottleneck(self, bottlenecks: List[PerformanceBottleneck]) -> Optional[PerformanceBottleneck]:
        """Identify the primary bottleneck from detected bottlenecks."""
        if not bottlenecks:
            return None

        # Score bottlenecks based on severity, confidence, and impact
        def score_bottleneck(bottleneck: PerformanceBottleneck) -> float:
            severity_scores = {
                BottleneckSeverity.LOW: 1.0,
                BottleneckSeverity.MODERATE: 2.0,
                BottleneckSeverity.HIGH: 3.0,
                BottleneckSeverity.CRITICAL: 4.0
            }

            severity_score = severity_scores.get(bottleneck.severity, 1.0)
            return severity_score * bottleneck.confidence * bottleneck.impact_score

        # Return bottleneck with highest score
        return max(bottlenecks, key=score_bottleneck)

    def _calculate_system_efficiency(self, metrics: List[ResourceMetrics]) -> float:
        """Calculate overall system efficiency score."""
        if not metrics:
            return 0.0

        # Calculate efficiency based on resource utilization balance
        cpu_usage = [m.cpu_usage_percent for m in metrics]
        memory_usage = [m.memory_usage_percent for m in metrics]

        avg_cpu = statistics.mean(cpu_usage)
        avg_memory = statistics.mean(memory_usage)

        # Ideal utilization is around 70-80%
        ideal_utilization = 75.0

        cpu_efficiency = 1.0 - abs(avg_cpu - ideal_utilization) / 100.0
        memory_efficiency = 1.0 - abs(avg_memory - ideal_utilization) / 100.0

        # Overall efficiency is the average, weighted by importance
        overall_efficiency = (cpu_efficiency * 0.4 + memory_efficiency * 0.4) + 0.2

        return max(0.0, min(1.0, overall_efficiency))

    def _generate_recommendations(self, bottlenecks: List[PerformanceBottleneck]) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations for detected bottlenecks."""
        recommendations = []

        for bottleneck in bottlenecks:
            bottleneck_recommendations = self.get_recommendations(bottleneck.bottleneck_type)

            # Filter and prioritize recommendations based on bottleneck severity
            for rec in bottleneck_recommendations:
                if bottleneck.severity in [BottleneckSeverity.HIGH, BottleneckSeverity.CRITICAL]:
                    # Prioritize high-impact recommendations for severe bottlenecks
                    if rec.expected_improvement > 20:
                        recommendations.append(rec)
                elif bottleneck.severity == BottleneckSeverity.MODERATE:
                    # Include moderate-impact recommendations
                    if rec.expected_improvement > 10:
                        recommendations.append(rec)
                else:
                    # Include all recommendations for low severity
                    recommendations.append(rec)

        # Remove duplicates and sort by expected improvement
        unique_recommendations = []
        seen_strategies = set()

        for rec in sorted(recommendations, key=lambda x: x.expected_improvement, reverse=True):
            if rec.strategy not in seen_strategies:
                unique_recommendations.append(rec)
                seen_strategies.add(rec.strategy)

        return unique_recommendations[:10]  # Limit to top 10 recommendations

    def _calculate_analysis_confidence(self, bottlenecks: List[PerformanceBottleneck]) -> float:
        """Calculate overall confidence in the analysis."""
        if not bottlenecks:
            return 0.5  # Moderate confidence when no bottlenecks detected

        # Average confidence of all detected bottlenecks
        avg_confidence = statistics.mean([b.confidence for b in bottlenecks])

        # Adjust based on number of bottlenecks (more bottlenecks = higher confidence)
        confidence_boost = min(0.2, len(bottlenecks) * 0.05)

        return min(1.0, avg_confidence + confidence_boost)

    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction for a series of values."""
        if len(values) < 3:
            return "stable"

        # Simple linear regression to determine trend
        x = list(range(len(values)))
        n = len(values)

        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))

        # Calculate slope
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)

        if slope > 1.0:
            return "increasing"
        elif slope < -1.0:
            return "decreasing"
        else:
            return "stable"

    def _calculate_contention_score(self, values: List[float]) -> float:
        """Calculate resource contention score based on usage patterns."""
        if len(values) < 2:
            return 0.0

        # High variance indicates contention
        variance = statistics.variance(values)
        mean_value = statistics.mean(values)

        # Normalize variance by mean to get coefficient of variation
        cv = variance / (mean_value + 1e-8)

        # Convert to 0-1 score
        return min(1.0, cv / 10.0)

    def _calculate_efficiency_score(self, values: List[float]) -> float:
        """Calculate resource efficiency score."""
        if not values:
            return 0.0

        avg_usage = statistics.mean(values)

        # Efficiency is highest around 70-80% utilization
        if 70 <= avg_usage <= 80:
            return 1.0
        elif 60 <= avg_usage < 70 or 80 < avg_usage <= 90:
            return 0.8
        elif 50 <= avg_usage < 60 or 90 < avg_usage <= 95:
            return 0.6
        elif avg_usage < 50 or avg_usage > 95:
            return 0.3
        else:
            return 0.5

    def _update_trend_data(self, metrics: ResourceMetrics) -> None:
        """Update trend analysis data."""
        # Keep only recent trend data
        max_points = self._config.trend_analysis_points

        self._trend_data['cpu'].append(metrics.cpu_usage_percent)
        if len(self._trend_data['cpu']) > max_points:
            self._trend_data['cpu'] = self._trend_data['cpu'][-max_points:]

        self._trend_data['memory'].append(metrics.memory_usage_percent)
        if len(self._trend_data['memory']) > max_points:
            self._trend_data['memory'] = self._trend_data['memory'][-max_points:]

        # Add GPU data if available
        if hasattr(metrics, 'gpu_usage_percent'):
            self._trend_data['gpu'].append(metrics.gpu_usage_percent)
            if len(self._trend_data['gpu']) > max_points:
                self._trend_data['gpu'] = self._trend_data['gpu'][-max_points:]

    async def _check_real_time_bottlenecks(self) -> None:
        """Check for real-time bottlenecks and update current state."""
        try:
            bottlenecks = await self.detect_real_time_bottlenecks()

            with self._lock:
                # Update current bottlenecks
                self._current_bottlenecks = bottlenecks

                # Add to history if significant
                for bottleneck in bottlenecks:
                    if bottleneck.severity in [BottleneckSeverity.HIGH, BottleneckSeverity.CRITICAL]:
                        self._bottleneck_history.append(bottleneck)

                        # Limit history size
                        if len(self._bottleneck_history) > 100:
                            self._bottleneck_history = self._bottleneck_history[-100:]

        except Exception as e:
            self._logger.error(f"Error in real-time bottleneck check: {e}")

    def _initialize_optimization_strategies(self) -> Dict[BottleneckType, List[OptimizationRecommendation]]:
        """Initialize the optimization strategies knowledge base."""
        strategies = {
            BottleneckType.CPU_BOUND: [
                OptimizationRecommendation(
                    strategy=OptimizationStrategy.INCREASE_PARALLELISM,
                    description="Increase parallel processing threads and optimize CPU-intensive operations",
                    expected_improvement=25.0,
                    implementation_difficulty="Moderate",
                    estimated_time_hours=4.0,
                    prerequisites=["Multi-core CPU", "Thread-safe code"],
                    risks=["Increased memory usage", "Potential race conditions"],
                    metrics_to_monitor=["CPU usage", "Thread count", "Context switches"]
                ),
                OptimizationRecommendation(
                    strategy=OptimizationStrategy.OPTIMIZE_ALGORITHMS,
                    description="Profile and optimize CPU-intensive algorithms and data structures",
                    expected_improvement=30.0,
                    implementation_difficulty="Hard",
                    estimated_time_hours=8.0,
                    prerequisites=["Profiling tools", "Algorithm expertise"],
                    risks=["Code complexity", "Potential bugs"],
                    metrics_to_monitor=["CPU usage", "Execution time", "Algorithm efficiency"]
                )
            ],

            BottleneckType.MEMORY_BOUND: [
                OptimizationRecommendation(
                    strategy=OptimizationStrategy.REDUCE_MEMORY_USAGE,
                    description="Optimize memory allocation patterns and reduce memory footprint",
                    expected_improvement=35.0,
                    implementation_difficulty="Moderate",
                    estimated_time_hours=6.0,
                    prerequisites=["Memory profiling tools"],
                    risks=["Reduced functionality", "Performance trade-offs"],
                    metrics_to_monitor=["Memory usage", "Allocation rate", "GC pressure"]
                ),
                OptimizationRecommendation(
                    strategy=OptimizationStrategy.MEMORY_POOLING,
                    description="Implement memory pooling to reduce allocation overhead",
                    expected_improvement=20.0,
                    implementation_difficulty="Moderate",
                    estimated_time_hours=5.0,
                    prerequisites=["Memory management expertise"],
                    risks=["Memory fragmentation", "Complexity"],
                    metrics_to_monitor=["Memory usage", "Allocation count", "Pool efficiency"]
                )
            ],

            BottleneckType.GPU_BOUND: [
                OptimizationRecommendation(
                    strategy=OptimizationStrategy.ADJUST_BATCH_SIZE,
                    description="Optimize GPU batch sizes for better utilization",
                    expected_improvement=25.0,
                    implementation_difficulty="Easy",
                    estimated_time_hours=2.0,
                    prerequisites=["GPU monitoring tools"],
                    risks=["Memory overflow", "Reduced accuracy"],
                    metrics_to_monitor=["GPU usage", "Memory usage", "Throughput"]
                ),
                OptimizationRecommendation(
                    strategy=OptimizationStrategy.UPGRADE_HARDWARE,
                    description="Consider GPU upgrade or additional GPU resources",
                    expected_improvement=50.0,
                    implementation_difficulty="Easy",
                    estimated_time_hours=1.0,
                    prerequisites=["Budget", "Compatible hardware"],
                    risks=["Cost", "Power consumption"],
                    metrics_to_monitor=["GPU usage", "Performance metrics"]
                )
            ],

            BottleneckType.DISK_IO_BOUND: [
                OptimizationRecommendation(
                    strategy=OptimizationStrategy.OPTIMIZE_DISK_ACCESS,
                    description="Optimize disk I/O patterns and implement caching strategies",
                    expected_improvement=40.0,
                    implementation_difficulty="Moderate",
                    estimated_time_hours=6.0,
                    prerequisites=["I/O profiling tools"],
                    risks=["Data consistency", "Cache invalidation"],
                    metrics_to_monitor=["Disk I/O", "Cache hit rate", "Latency"]
                ),
                OptimizationRecommendation(
                    strategy=OptimizationStrategy.ENABLE_CACHING,
                    description="Implement intelligent caching for frequently accessed data",
                    expected_improvement=30.0,
                    implementation_difficulty="Moderate",
                    estimated_time_hours=4.0,
                    prerequisites=["Cache management system"],
                    risks=["Memory usage", "Cache coherence"],
                    metrics_to_monitor=["Cache hit rate", "Memory usage", "I/O reduction"]
                )
            ],

            BottleneckType.THERMAL_THROTTLING: [
                OptimizationRecommendation(
                    strategy=OptimizationStrategy.IMPROVE_THERMAL_MANAGEMENT,
                    description="Improve cooling and thermal management strategies",
                    expected_improvement=20.0,
                    implementation_difficulty="Easy",
                    estimated_time_hours=2.0,
                    prerequisites=["Thermal monitoring"],
                    risks=["Hardware modifications"],
                    metrics_to_monitor=["Temperature", "Fan speed", "Throttling events"]
                )
            ],

            BottleneckType.MEMORY_BANDWIDTH: [
                OptimizationRecommendation(
                    strategy=OptimizationStrategy.OPTIMIZE_ALGORITHMS,
                    description="Optimize memory access patterns to reduce bandwidth pressure",
                    expected_improvement=25.0,
                    implementation_difficulty="Hard",
                    estimated_time_hours=8.0,
                    prerequisites=["Memory profiling", "Algorithm expertise"],
                    risks=["Code complexity"],
                    metrics_to_monitor=["Memory bandwidth", "Cache efficiency", "Access patterns"]
                )
            ]
        }

        return strategies

    def get_configuration(self) -> BottleneckConfiguration:
        """Get current bottleneck detection configuration."""
        return self._config

    def update_configuration(self, config: BottleneckConfiguration) -> None:
        """Update bottleneck detection configuration."""
        with self._lock:
            self._config = config

        self._logger.info("Bottleneck detection configuration updated")

    def get_bottleneck_history(self) -> List[PerformanceBottleneck]:
        """Get history of detected bottlenecks."""
        with self._lock:
            return self._bottleneck_history.copy()

    def get_current_bottlenecks(self) -> List[PerformanceBottleneck]:
        """Get currently detected bottlenecks."""
        with self._lock:
            return self._current_bottlenecks.copy()

    def get_system_health_score(self) -> float:
        """Calculate overall system health score."""
        recent_metrics = self._get_recent_metrics(minutes=5)
        if not recent_metrics:
            return 0.5

        # Calculate health based on resource utilization
        cpu_usage = [m.cpu_usage_percent for m in recent_metrics]
        memory_usage = [m.memory_usage_percent for m in recent_metrics]

        avg_cpu = statistics.mean(cpu_usage)
        avg_memory = statistics.mean(memory_usage)

        # Health decreases as utilization approaches limits
        cpu_health = max(0, 1 - (avg_cpu / 100))
        memory_health = max(0, 1 - (avg_memory / 100))

        # Check for active bottlenecks
        bottleneck_penalty = len(self._current_bottlenecks) * 0.1

        overall_health = (cpu_health + memory_health) / 2 - bottleneck_penalty

        return max(0.0, min(1.0, overall_health))
