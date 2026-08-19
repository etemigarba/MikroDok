"""
Module: health_monitor_lg
Description: Service health monitoring, status tracking, alerting, and health metrics collection
Phase: 4
Location: /src/modules/logic/background_services_lg/health_monitor_lg/
"""

# Standard library imports
import asyncio
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Set
import uuid
import statistics
import weakref

# Local imports
from ..base_interfaces import (
    IHealthMonitor, HealthCheck, HealthMetrics, ServiceAlert, HealthStatus,
    AlertLevel, HealthMonitorConfig, HealthCheckResult
)
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.error_handling_lg import ErrorClassifier, ErrorSeverity


class ServiceHealthTracker:
    """
    Tracks health metrics for individual services.
    
    Features:
    - Real-time health monitoring
    - Historical metrics storage
    - Trend analysis
    - Performance tracking
    """
    
    def __init__(self, service_id: str, retention_hours: int = 24):
        """Initialize service health tracker."""
        self._logger = get_logger(__name__)
        self._service_id = service_id
        self._retention_hours = retention_hours
        
        # Metrics storage
        self._metrics_history: deque = deque(maxlen=1000)  # Last 1000 metrics
        self._current_metrics: Optional[HealthMetrics] = None
        
        # Health checks
        self._health_checks: Dict[str, HealthCheck] = {}
        self._check_results: Dict[str, List[HealthCheckResult]] = defaultdict(list)
        
        # Thread safety
        self._lock = threading.RLock()
        
        self._logger.debug(f"Health tracker initialized for service {service_id}")
    
    def add_health_check(self, health_check: HealthCheck) -> bool:
        """Add a health check for this service."""
        try:
            with self._lock:
                self._health_checks[health_check.check_id] = health_check
                self._logger.debug(f"Added health check {health_check.check_id} for service {self._service_id}")
                return True
                
        except Exception as e:
            self._logger.error(f"Error adding health check {health_check.check_id}: {e}")
            return False
    
    def remove_health_check(self, check_id: str) -> bool:
        """Remove a health check."""
        try:
            with self._lock:
                removed = self._health_checks.pop(check_id, None)
                if removed:
                    self._check_results.pop(check_id, None)
                    self._logger.debug(f"Removed health check {check_id} for service {self._service_id}")
                    return True
                return False
                
        except Exception as e:
            self._logger.error(f"Error removing health check {check_id}: {e}")
            return False
    
    def update_metrics(self, metrics: HealthMetrics) -> None:
        """Update current health metrics."""
        try:
            with self._lock:
                self._current_metrics = metrics
                self._metrics_history.append(metrics)
                
                # Clean up old metrics
                self._cleanup_old_metrics()
                
        except Exception as e:
            self._logger.error(f"Error updating metrics for service {self._service_id}: {e}")
    
    def get_current_metrics(self) -> Optional[HealthMetrics]:
        """Get current health metrics."""
        with self._lock:
            return self._current_metrics
    
    def get_metrics_history(self, hours: int = 1) -> List[HealthMetrics]:
        """Get historical metrics."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            return [
                metrics for metrics in self._metrics_history
                if metrics.timestamp >= cutoff_time
            ]
    
    def get_health_checks(self) -> List[HealthCheck]:
        """Get all health checks for this service."""
        with self._lock:
            return list(self._health_checks.values())
    
    def add_check_result(self, result: HealthCheckResult) -> None:
        """Add a health check result."""
        try:
            with self._lock:
                self._check_results[result.check_id].append(result)
                
                # Limit result history
                if len(self._check_results[result.check_id]) > 100:
                    self._check_results[result.check_id] = self._check_results[result.check_id][-100:]
                
        except Exception as e:
            self._logger.error(f"Error adding check result for {result.check_id}: {e}")
    
    def get_check_results(self, check_id: str, limit: int = 10) -> List[HealthCheckResult]:
        """Get recent check results."""
        with self._lock:
            results = self._check_results.get(check_id, [])
            return results[-limit:] if results else []
    
    def calculate_health_score(self) -> float:
        """Calculate overall health score (0.0 to 1.0)."""
        try:
            with self._lock:
                if not self._current_metrics:
                    return 0.0
                
                score = 1.0
                
                # Factor in error rate
                if self._current_metrics.error_rate is not None:
                    error_penalty = min(self._current_metrics.error_rate / 100.0, 1.0)
                    score *= (1.0 - error_penalty)
                
                # Factor in response time (assume 1000ms is poor)
                if self._current_metrics.response_time is not None:
                    response_penalty = min(self._current_metrics.response_time / 1000.0, 1.0)
                    score *= (1.0 - response_penalty * 0.5)  # 50% weight
                
                # Factor in resource usage
                if self._current_metrics.cpu_usage is not None:
                    cpu_penalty = max(0, (self._current_metrics.cpu_usage - 80) / 20.0)  # Penalty above 80%
                    score *= (1.0 - cpu_penalty * 0.3)  # 30% weight
                
                if self._current_metrics.memory_usage is not None:
                    memory_gb = self._current_metrics.memory_usage / (1024 ** 3)
                    if memory_gb > 1.0:  # Penalty above 1GB
                        memory_penalty = min((memory_gb - 1.0) / 4.0, 1.0)  # Max penalty at 5GB
                        score *= (1.0 - memory_penalty * 0.2)  # 20% weight
                
                return max(0.0, min(1.0, score))
                
        except Exception as e:
            self._logger.error(f"Error calculating health score for service {self._service_id}: {e}")
            return 0.0
    
    def _cleanup_old_metrics(self) -> None:
        """Clean up old metrics beyond retention period."""
        cutoff_time = datetime.now() - timedelta(hours=self._retention_hours)
        
        # Remove old metrics from the beginning of deque
        while (self._metrics_history and 
               self._metrics_history[0].timestamp < cutoff_time):
            self._metrics_history.popleft()


class AlertManager:
    """
    Manages service alerts and notifications.
    
    Features:
    - Alert creation and management
    - Alert escalation
    - Notification routing
    - Alert suppression
    """
    
    def __init__(self):
        """Initialize alert manager."""
        self._logger = get_logger(__name__)
        
        # Alert storage
        self._active_alerts: Dict[str, ServiceAlert] = {}
        self._alert_history: List[ServiceAlert] = []
        
        # Alert suppression
        self._suppressed_alerts: Set[str] = set()
        self._suppression_rules: Dict[str, timedelta] = {}
        
        # Thread safety
        self._lock = threading.RLock()
    
    def create_alert(self, alert: ServiceAlert) -> bool:
        """Create a new service alert."""
        try:
            with self._lock:
                # Check if alert is suppressed
                if self._is_alert_suppressed(alert):
                    self._logger.debug(f"Alert {alert.alert_id} suppressed")
                    return False
                
                # Store alert
                self._active_alerts[alert.alert_id] = alert
                self._alert_history.append(alert)
                
                # Limit history size
                if len(self._alert_history) > 10000:
                    self._alert_history = self._alert_history[-10000:]
                
                self._logger.warning(f"Alert created: {alert.level.value} - {alert.message} (Service: {alert.service_id})")
                return True
                
        except Exception as e:
            self._logger.error(f"Error creating alert {alert.alert_id}: {e}")
            return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an active alert."""
        try:
            with self._lock:
                alert = self._active_alerts.get(alert_id)
                if not alert:
                    return False
                
                alert.resolved = True
                alert.resolved_at = datetime.now()
                
                # Remove from active alerts
                del self._active_alerts[alert_id]
                
                self._logger.info(f"Alert resolved: {alert_id}")
                return True
                
        except Exception as e:
            self._logger.error(f"Error resolving alert {alert_id}: {e}")
            return False
    
    def get_active_alerts(self, service_id: Optional[str] = None, level: Optional[AlertLevel] = None) -> List[ServiceAlert]:
        """Get active alerts."""
        with self._lock:
            alerts = list(self._active_alerts.values())
            
            if service_id:
                alerts = [a for a in alerts if a.service_id == service_id]
            
            if level:
                alerts = [a for a in alerts if a.level == level]
            
            return alerts
    
    def get_alert_history(self, service_id: Optional[str] = None, hours: int = 24) -> List[ServiceAlert]:
        """Get alert history."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            alerts = [
                alert for alert in self._alert_history
                if alert.timestamp >= cutoff_time
            ]
            
            if service_id:
                alerts = [a for a in alerts if a.service_id == service_id]
            
            return alerts
    
    def suppress_alert_type(self, service_id: str, alert_pattern: str, duration: timedelta) -> None:
        """Suppress alerts matching a pattern for a duration."""
        with self._lock:
            suppression_key = f"{service_id}:{alert_pattern}"
            self._suppressed_alerts.add(suppression_key)
            self._suppression_rules[suppression_key] = duration
            
            self._logger.info(f"Alert suppression added: {suppression_key} for {duration}")
    
    def _is_alert_suppressed(self, alert: ServiceAlert) -> bool:
        """Check if an alert is suppressed."""
        # Simple pattern matching - could be enhanced with regex
        suppression_key = f"{alert.service_id}:*"
        return suppression_key in self._suppressed_alerts
    
    def cleanup_resolved_alerts(self, max_age_hours: int = 24) -> int:
        """Clean up old resolved alerts."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        with self._lock:
            original_count = len(self._alert_history)
            self._alert_history = [
                alert for alert in self._alert_history
                if not alert.resolved or alert.resolved_at is None or alert.resolved_at >= cutoff_time
            ]
            
            cleaned_count = original_count - len(self._alert_history)
            if cleaned_count > 0:
                self._logger.debug(f"Cleaned up {cleaned_count} old resolved alerts")
            
            return cleaned_count


class HealthMetricsCollector:
    """
    Collects and aggregates health metrics from multiple sources.
    
    Features:
    - Multi-source metric collection
    - Metric aggregation
    - Statistical analysis
    - Performance trending
    """
    
    def __init__(self):
        """Initialize health metrics collector."""
        self._logger = get_logger(__name__)
        
        # Metric collectors
        self._collectors: Dict[str, Callable] = {}
        self._collection_intervals: Dict[str, timedelta] = {}
        self._last_collection: Dict[str, datetime] = {}
        
        # Aggregated metrics
        self._aggregated_metrics: Dict[str, Any] = {}
        
        # Thread safety
        self._lock = threading.RLock()
    
    def register_collector(self, name: str, collector_func: Callable, interval: timedelta) -> bool:
        """Register a metric collector."""
        try:
            with self._lock:
                self._collectors[name] = collector_func
                self._collection_intervals[name] = interval
                self._last_collection[name] = datetime.min
                
                self._logger.debug(f"Registered metric collector: {name}")
                return True
                
        except Exception as e:
            self._logger.error(f"Error registering collector {name}: {e}")
            return False
    
    def unregister_collector(self, name: str) -> bool:
        """Unregister a metric collector."""
        try:
            with self._lock:
                removed = self._collectors.pop(name, None)
                if removed:
                    self._collection_intervals.pop(name, None)
                    self._last_collection.pop(name, None)
                    self._aggregated_metrics.pop(name, None)
                    
                    self._logger.debug(f"Unregistered metric collector: {name}")
                    return True
                return False
                
        except Exception as e:
            self._logger.error(f"Error unregistering collector {name}: {e}")
            return False
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect metrics from all registered collectors."""
        results = {}
        current_time = datetime.now()
        
        with self._lock:
            collectors_to_run = []
            
            for name, collector in self._collectors.items():
                interval = self._collection_intervals[name]
                last_run = self._last_collection[name]
                
                if current_time - last_run >= interval:
                    collectors_to_run.append((name, collector))
        
        # Run collectors outside of lock
        for name, collector in collectors_to_run:
            try:
                if asyncio.iscoroutinefunction(collector):
                    result = await collector()
                else:
                    result = collector()
                
                results[name] = result
                
                with self._lock:
                    self._last_collection[name] = current_time
                    self._aggregated_metrics[name] = result
                
            except Exception as e:
                self._logger.error(f"Error collecting metrics from {name}: {e}")
                results[name] = {'error': str(e)}
        
        return results
    
    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """Get current aggregated metrics."""
        with self._lock:
            return self._aggregated_metrics.copy()
    
    def calculate_system_health_score(self) -> float:
        """Calculate overall system health score."""
        try:
            with self._lock:
                if not self._aggregated_metrics:
                    return 0.0
                
                scores = []
                
                for name, metrics in self._aggregated_metrics.items():
                    if isinstance(metrics, dict) and 'health_score' in metrics:
                        scores.append(metrics['health_score'])
                    elif isinstance(metrics, dict) and 'status' in metrics:
                        # Convert status to score
                        status = metrics['status']
                        if status == 'healthy':
                            scores.append(1.0)
                        elif status == 'warning':
                            scores.append(0.7)
                        elif status == 'critical':
                            scores.append(0.3)
                        else:
                            scores.append(0.0)
                
                if not scores:
                    return 0.0
                
                # Calculate weighted average (could be enhanced with weights)
                return statistics.mean(scores)
                
        except Exception as e:
            self._logger.error(f"Error calculating system health score: {e}")
            return 0.0


class HealthMonitor(IHealthMonitor):
    """
    Main health monitor implementation.

    Features:
    - Service health monitoring
    - Health check execution
    - Alert management
    - Metrics collection and analysis
    - Automated health reporting
    """

    def __init__(self, config: Optional[HealthMonitorConfig] = None):
        """Initialize health monitor."""
        self._logger = get_logger(__name__)
        self._config = config or HealthMonitorConfig()

        # Core components
        self._service_trackers: Dict[str, ServiceHealthTracker] = {}
        self._alert_manager = AlertManager()
        self._metrics_collector = HealthMetricsCollector()

        # Health checks
        self._health_checks: Dict[str, HealthCheck] = {}

        # Monitoring state
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._check_tasks: Dict[str, asyncio.Task] = {}

        # Thread safety
        self._lock = threading.RLock()

        self._logger.info("Health monitor initialized")

    def register_health_check(self, health_check: HealthCheck) -> bool:
        """Register a health check."""
        try:
            with self._lock:
                self._health_checks[health_check.check_id] = health_check

                # Add to service tracker
                if health_check.service_id not in self._service_trackers:
                    self._service_trackers[health_check.service_id] = ServiceHealthTracker(
                        health_check.service_id,
                        retention_hours=int(self._config.metrics_retention.total_seconds() / 3600)
                    )

                self._service_trackers[health_check.service_id].add_health_check(health_check)

                self._logger.info(f"Registered health check {health_check.check_id} for service {health_check.service_id}")
                return True

        except Exception as e:
            self._logger.error(f"Error registering health check {health_check.check_id}: {e}")
            return False

    def unregister_health_check(self, check_id: str) -> bool:
        """Unregister a health check."""
        try:
            with self._lock:
                health_check = self._health_checks.pop(check_id, None)
                if not health_check:
                    return False

                # Remove from service tracker
                tracker = self._service_trackers.get(health_check.service_id)
                if tracker:
                    tracker.remove_health_check(check_id)

                # Cancel running check
                if check_id in self._check_tasks:
                    self._check_tasks[check_id].cancel()
                    del self._check_tasks[check_id]

                self._logger.info(f"Unregistered health check {check_id}")
                return True

        except Exception as e:
            self._logger.error(f"Error unregistering health check {check_id}: {e}")
            return False

    async def execute_health_check(self, check_id: str) -> HealthCheckResult:
        """Execute a specific health check."""
        try:
            health_check = self._health_checks.get(check_id)
            if not health_check:
                message = f"Health check {check_id} not found"
                self._logger.error(message)
                return HealthCheckResult(
                    success=False,
                    check_id=check_id,
                    status=HealthStatus.UNKNOWN,
                    metrics=HealthMetrics(
                        service_id="unknown",
                        status=HealthStatus.UNKNOWN,
                        timestamp=datetime.now()
                    ),
                    message=message
                )

            start_time = datetime.now()

            try:
                # Execute health check with timeout
                if asyncio.iscoroutinefunction(health_check.check_function):
                    result = await asyncio.wait_for(
                        health_check.check_function(),
                        timeout=health_check.timeout.total_seconds()
                    )
                else:
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, health_check.check_function),
                        timeout=health_check.timeout.total_seconds()
                    )

                end_time = datetime.now()
                response_time = (end_time - start_time).total_seconds() * 1000  # ms

                # Create health metrics
                metrics = HealthMetrics(
                    service_id=health_check.service_id,
                    status=HealthStatus.HEALTHY,
                    timestamp=end_time,
                    response_time=response_time
                )

                # Update service tracker
                tracker = self._service_trackers.get(health_check.service_id)
                if tracker:
                    tracker.update_metrics(metrics)

                # Reset consecutive failures
                health_check.consecutive_failures = 0
                health_check.last_check = end_time

                check_result = HealthCheckResult(
                    success=True,
                    check_id=check_id,
                    status=HealthStatus.HEALTHY,
                    metrics=metrics,
                    message="Health check passed"
                )

                # Add result to tracker
                if tracker:
                    tracker.add_check_result(check_result)

                return check_result

            except asyncio.TimeoutError:
                self._logger.warning(f"Health check {check_id} timed out")
                return await self._handle_check_failure(health_check, "Health check timed out")

            except Exception as e:
                self._logger.error(f"Health check {check_id} failed: {e}")
                return await self._handle_check_failure(health_check, str(e))

        except Exception as e:
            error_msg = f"Error executing health check {check_id}: {e}"
            self._logger.error(error_msg)

            return HealthCheckResult(
                success=False,
                check_id=check_id,
                status=HealthStatus.UNKNOWN,
                metrics=HealthMetrics(
                    service_id="unknown",
                    status=HealthStatus.UNKNOWN,
                    timestamp=datetime.now()
                ),
                message=error_msg
            )

    def get_service_health(self, service_id: str) -> Optional[HealthMetrics]:
        """Get current health metrics for a service."""
        tracker = self._service_trackers.get(service_id)
        return tracker.get_current_metrics() if tracker else None

    def get_health_history(self, service_id: str, hours: int = 24) -> List[HealthMetrics]:
        """Get health metrics history."""
        tracker = self._service_trackers.get(service_id)
        return tracker.get_metrics_history(hours) if tracker else []

    def create_alert(self, alert: ServiceAlert) -> bool:
        """Create a service alert."""
        return self._alert_manager.create_alert(alert)

    def get_active_alerts(self, service_id: Optional[str] = None) -> List[ServiceAlert]:
        """Get active alerts."""
        return self._alert_manager.get_active_alerts(service_id)

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        return self._alert_manager.resolve_alert(alert_id)

    async def start_monitoring(self) -> None:
        """Start health monitoring."""
        if self._running:
            self._logger.warning("Health monitoring is already running")
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())

        self._logger.info("Health monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        if not self._running:
            return

        self._running = False

        # Cancel monitor task
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Cancel all check tasks
        for task in self._check_tasks.values():
            task.cancel()

        # Wait for tasks to complete
        if self._check_tasks:
            await asyncio.gather(*self._check_tasks.values(), return_exceptions=True)

        self._check_tasks.clear()

        self._logger.info("Health monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                current_time = datetime.now()

                # Check which health checks need to run
                checks_to_run = []

                with self._lock:
                    for check_id, health_check in self._health_checks.items():
                        if not health_check.enabled:
                            continue

                        # Check if it's time to run
                        if (health_check.last_check is None or
                            current_time - health_check.last_check >= health_check.interval):

                            # Don't run if already running
                            if check_id not in self._check_tasks or self._check_tasks[check_id].done():
                                checks_to_run.append(check_id)

                # Start health checks
                for check_id in checks_to_run:
                    task = asyncio.create_task(self.execute_health_check(check_id))
                    self._check_tasks[check_id] = task

                # Clean up completed tasks
                completed_tasks = []
                for check_id, task in self._check_tasks.items():
                    if task.done():
                        completed_tasks.append(check_id)

                for check_id in completed_tasks:
                    del self._check_tasks[check_id]

                # Collect metrics
                await self._metrics_collector.collect_metrics()

                # Clean up old alerts
                self._alert_manager.cleanup_resolved_alerts()

                # Sleep for a short interval
                await asyncio.sleep(10)  # Check every 10 seconds

            except Exception as e:
                self._logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)

    async def _handle_check_failure(self, health_check: HealthCheck, error_message: str) -> HealthCheckResult:
        """Handle health check failure."""
        health_check.consecutive_failures += 1
        health_check.last_check = datetime.now()

        # Determine status based on consecutive failures
        if health_check.consecutive_failures >= health_check.max_failures:
            status = HealthStatus.CRITICAL
        else:
            status = HealthStatus.WARNING

        # Create metrics
        metrics = HealthMetrics(
            service_id=health_check.service_id,
            status=status,
            timestamp=datetime.now(),
            error_rate=100.0  # 100% error rate for failed check
        )

        # Update service tracker
        tracker = self._service_trackers.get(health_check.service_id)
        if tracker:
            tracker.update_metrics(metrics)

        # Create alert if threshold reached
        if health_check.consecutive_failures >= health_check.max_failures:
            alert = ServiceAlert(
                alert_id=str(uuid.uuid4()),
                service_id=health_check.service_id,
                level=AlertLevel.CRITICAL,
                message=f"Health check {health_check.name} failed {health_check.consecutive_failures} times: {error_message}",
                timestamp=datetime.now()
            )
            self.create_alert(alert)

        check_result = HealthCheckResult(
            success=False,
            check_id=health_check.check_id,
            status=status,
            metrics=metrics,
            message=error_message
        )

        # Add result to tracker
        if tracker:
            tracker.add_check_result(check_result)

        return check_result
