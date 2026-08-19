"""
Module: performance_metrics_db
Description: Stores historical performance data for analysis with efficient aggregation and reporting for system optimization and monitoring
Phase: 4
Location: /src/modules/database/system_logs_db/performance_metrics_db/
"""

# Standard library imports
import sqlite3
import threading
import json
import statistics
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from uuid import uuid4

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class MetricType(Enum):
    """Performance metric type enumeration."""
    CPU_USAGE = "CPU_USAGE"
    MEMORY_USAGE = "MEMORY_USAGE"
    DISK_USAGE = "DISK_USAGE"
    NETWORK_USAGE = "NETWORK_USAGE"
    GPU_USAGE = "GPU_USAGE"
    RESPONSE_TIME = "RESPONSE_TIME"
    THROUGHPUT = "THROUGHPUT"
    LATENCY = "LATENCY"
    ERROR_RATE = "ERROR_RATE"
    TRAINING_SPEED = "TRAINING_SPEED"
    INFERENCE_SPEED = "INFERENCE_SPEED"
    MODEL_ACCURACY = "MODEL_ACCURACY"
    BATCH_PROCESSING_TIME = "BATCH_PROCESSING_TIME"
    QUEUE_LENGTH = "QUEUE_LENGTH"
    CONNECTION_COUNT = "CONNECTION_COUNT"
    CACHE_HIT_RATE = "CACHE_HIT_RATE"


class MetricCategory(Enum):
    """Performance metric category enumeration."""
    SYSTEM = "SYSTEM"
    APPLICATION = "APPLICATION"
    DATABASE = "DATABASE"
    NETWORK = "NETWORK"
    TRAINING = "TRAINING"
    INFERENCE = "INFERENCE"
    USER_EXPERIENCE = "USER_EXPERIENCE"
    RESOURCE_UTILIZATION = "RESOURCE_UTILIZATION"
    BUSINESS = "BUSINESS"


class AggregationType(Enum):
    """Aggregation type enumeration."""
    AVERAGE = "AVERAGE"
    MINIMUM = "MINIMUM"
    MAXIMUM = "MAXIMUM"
    SUM = "SUM"
    COUNT = "COUNT"
    MEDIAN = "MEDIAN"
    PERCENTILE_95 = "PERCENTILE_95"
    PERCENTILE_99 = "PERCENTILE_99"
    STANDARD_DEVIATION = "STANDARD_DEVIATION"


@dataclass
class PerformanceMetric:
    """Performance metric data structure."""
    metric_id: str
    timestamp: datetime
    metric_type: MetricType
    category: MetricCategory
    source: str
    value: float
    unit: str
    tags: Optional[Dict[str, str]] = None
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None


@dataclass
class MetricAggregation:
    """Metric aggregation data structure."""
    aggregation_id: str
    metric_type: MetricType
    category: MetricCategory
    aggregation_type: AggregationType
    time_period: str  # e.g., "1h", "1d", "1w"
    start_time: datetime
    end_time: datetime
    value: float
    sample_count: int
    source_filter: Optional[str] = None


class PerformanceMetricsDB:
    """
    Performance metrics database manager.
    
    Stores historical performance data with efficient aggregation, indexing,
    and reporting capabilities for comprehensive system optimization,
    monitoring, and trend analysis.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the performance metrics database.
        
        Args:
            db_path: Path to the database file
        """
        if db_path is None:
            # Default to system logs data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "system_logs"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "performance_metrics.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        
        # Retention settings
        self._raw_retention_days = 7      # Keep raw metrics for 7 days
        self._hourly_retention_days = 90  # Keep hourly aggregations for 90 days
        self._daily_retention_months = 12 # Keep daily aggregations for 12 months
        self._weekly_retention_years = 5  # Keep weekly aggregations for 5 years
        
        # Performance settings
        self._batch_size = 1000
        self._aggregation_interval_minutes = 5  # Aggregate every 5 minutes
        
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            # Create performance metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    metric_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    source TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT NOT NULL,
                    tags TEXT,
                    context TEXT,
                    session_id TEXT,
                    correlation_id TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create metric aggregations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metric_aggregations (
                    aggregation_id TEXT PRIMARY KEY,
                    metric_type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    aggregation_type TEXT NOT NULL,
                    time_period TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    value REAL NOT NULL,
                    sample_count INTEGER NOT NULL,
                    source_filter TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create metric thresholds table for alerting
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metric_thresholds (
                    threshold_id TEXT PRIMARY KEY,
                    metric_type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    source_pattern TEXT,
                    warning_threshold REAL,
                    critical_threshold REAL,
                    comparison_operator TEXT NOT NULL DEFAULT 'GT',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create metric alerts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metric_alerts (
                    alert_id TEXT PRIMARY KEY,
                    threshold_id TEXT NOT NULL,
                    metric_id TEXT NOT NULL,
                    alert_level TEXT NOT NULL,
                    triggered_at TEXT NOT NULL,
                    resolved_at TEXT,
                    current_value REAL NOT NULL,
                    threshold_value REAL NOT NULL,
                    message TEXT,
                    acknowledged INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (threshold_id) REFERENCES metric_thresholds (threshold_id),
                    FOREIGN KEY (metric_id) REFERENCES performance_metrics (metric_id)
                )
            """)
            
            # Create indexes for efficient querying
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp ON performance_metrics(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_metrics_type ON performance_metrics(metric_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_metrics_category ON performance_metrics(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_metrics_source ON performance_metrics(source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_metrics_session_id ON performance_metrics(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_metrics_correlation_id ON performance_metrics(correlation_id)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metric_aggregations_type_period ON metric_aggregations(metric_type, time_period)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metric_aggregations_start_time ON metric_aggregations(start_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metric_aggregations_category ON metric_aggregations(category)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metric_thresholds_type ON metric_thresholds(metric_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metric_thresholds_enabled ON metric_thresholds(enabled)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metric_alerts_triggered_at ON metric_alerts(triggered_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metric_alerts_resolved_at ON metric_alerts(resolved_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metric_alerts_acknowledged ON metric_alerts(acknowledged)")
            
            conn.commit()
            conn.close()
            
            self._logger.info("Performance metrics database initialized successfully")
    
    def record_metric(self, metric_type: MetricType, category: MetricCategory,
                     source: str, value: float, unit: str,
                     tags: Optional[Dict[str, str]] = None,
                     context: Optional[Dict[str, Any]] = None,
                     session_id: Optional[str] = None,
                     correlation_id: Optional[str] = None) -> str:
        """
        Record a new performance metric.
        
        Args:
            metric_type: Type of metric
            category: Metric category
            source: Source component or system
            value: Metric value
            unit: Unit of measurement
            tags: Optional tags for filtering and grouping
            context: Optional additional context
            session_id: Optional session ID
            correlation_id: Optional correlation ID for tracking related metrics
            
        Returns:
            Metric ID
        """
        metric_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)
        
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO performance_metrics (
                        metric_id, timestamp, metric_type, category, source,
                        value, unit, tags, context, session_id, correlation_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metric_id, timestamp.isoformat(), metric_type.value,
                    category.value, source, value, unit,
                    json.dumps(tags) if tags else None,
                    json.dumps(context) if context else None,
                    session_id, correlation_id
                ))
                
                conn.commit()
                conn.close()
                
                # Check thresholds for alerting
                self._check_metric_thresholds(metric_id, metric_type, category, source, value)
                
                return metric_id
                
            except Exception as e:
                self._logger.error(f"Failed to record metric: {e}")
                raise

    def _check_metric_thresholds(self, metric_id: str, metric_type: MetricType,
                                category: MetricCategory, source: str, value: float) -> None:
        """Check metric against defined thresholds and trigger alerts if needed."""
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Get applicable thresholds
                cursor.execute("""
                    SELECT threshold_id, warning_threshold, critical_threshold, comparison_operator
                    FROM metric_thresholds
                    WHERE metric_type = ? AND category = ? AND enabled = 1
                    AND (source_pattern IS NULL OR ? LIKE source_pattern)
                """, (metric_type.value, category.value, source))

                thresholds = cursor.fetchall()

                for threshold_id, warning_threshold, critical_threshold, operator in thresholds:
                    alert_level = None
                    threshold_value = None

                    # Check thresholds based on operator
                    if operator == 'GT':  # Greater than
                        if critical_threshold and value > critical_threshold:
                            alert_level = 'CRITICAL'
                            threshold_value = critical_threshold
                        elif warning_threshold and value > warning_threshold:
                            alert_level = 'WARNING'
                            threshold_value = warning_threshold
                    elif operator == 'LT':  # Less than
                        if critical_threshold and value < critical_threshold:
                            alert_level = 'CRITICAL'
                            threshold_value = critical_threshold
                        elif warning_threshold and value < warning_threshold:
                            alert_level = 'WARNING'
                            threshold_value = warning_threshold

                    # Create alert if threshold exceeded
                    if alert_level:
                        alert_id = str(uuid4())
                        message = f"{metric_type.value} {alert_level.lower()}: {value} {operator.lower()} {threshold_value}"

                        cursor.execute("""
                            INSERT INTO metric_alerts (
                                alert_id, threshold_id, metric_id, alert_level,
                                triggered_at, current_value, threshold_value, message
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            alert_id, threshold_id, metric_id, alert_level,
                            datetime.now(timezone.utc).isoformat(),
                            value, threshold_value, message
                        ))

                        self._logger.warning(f"Metric alert triggered: {message}")

                conn.commit()
                conn.close()

        except Exception as e:
            self._logger.error(f"Failed to check metric thresholds: {e}")

    def get_metrics(self, start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None,
                   metric_type: Optional[MetricType] = None,
                   category: Optional[MetricCategory] = None,
                   source: Optional[str] = None,
                   session_id: Optional[str] = None,
                   correlation_id: Optional[str] = None,
                   limit: int = 1000) -> List[PerformanceMetric]:
        """
        Retrieve performance metrics with filtering options.

        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter
            metric_type: Optional metric type filter
            category: Optional category filter
            source: Optional source filter
            session_id: Optional session ID filter
            correlation_id: Optional correlation ID filter
            limit: Maximum number of metrics to return

        Returns:
            List of performance metrics
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Build query with filters
                query = "SELECT * FROM performance_metrics WHERE 1=1"
                params = []

                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())

                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())

                if metric_type:
                    query += " AND metric_type = ?"
                    params.append(metric_type.value)

                if category:
                    query += " AND category = ?"
                    params.append(category.value)

                if source:
                    query += " AND source = ?"
                    params.append(source)

                if session_id:
                    query += " AND session_id = ?"
                    params.append(session_id)

                if correlation_id:
                    query += " AND correlation_id = ?"
                    params.append(correlation_id)

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                # Convert rows to PerformanceMetric objects
                metrics = []
                for row in rows:
                    metric = PerformanceMetric(
                        metric_id=row[0],
                        timestamp=datetime.fromisoformat(row[1]),
                        metric_type=MetricType(row[2]),
                        category=MetricCategory(row[3]),
                        source=row[4],
                        value=row[5],
                        unit=row[6],
                        tags=json.loads(row[7]) if row[7] else None,
                        context=json.loads(row[8]) if row[8] else None,
                        session_id=row[9],
                        correlation_id=row[10]
                    )
                    metrics.append(metric)

                return metrics

            except Exception as e:
                self._logger.error(f"Failed to get metrics: {e}")
                raise

    def create_aggregation(self, metric_type: MetricType, category: MetricCategory,
                          aggregation_type: AggregationType, time_period: str,
                          start_time: datetime, end_time: datetime,
                          source_filter: Optional[str] = None) -> str:
        """
        Create a metric aggregation for the specified time period.

        Args:
            metric_type: Type of metric to aggregate
            category: Metric category
            aggregation_type: Type of aggregation to perform
            time_period: Time period identifier (e.g., "1h", "1d")
            start_time: Start time for aggregation
            end_time: End time for aggregation
            source_filter: Optional source filter

        Returns:
            Aggregation ID
        """
        aggregation_id = str(uuid4())

        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Get metrics for aggregation
                query = """
                    SELECT value FROM performance_metrics
                    WHERE metric_type = ? AND category = ?
                    AND timestamp >= ? AND timestamp <= ?
                """
                params = [metric_type.value, category.value, start_time.isoformat(), end_time.isoformat()]

                if source_filter:
                    query += " AND source = ?"
                    params.append(source_filter)

                cursor.execute(query, params)
                values = [row[0] for row in cursor.fetchall()]

                if not values:
                    conn.close()
                    raise ValueError("No metrics found for aggregation")

                # Calculate aggregated value
                if aggregation_type == AggregationType.AVERAGE:
                    aggregated_value = statistics.mean(values)
                elif aggregation_type == AggregationType.MINIMUM:
                    aggregated_value = min(values)
                elif aggregation_type == AggregationType.MAXIMUM:
                    aggregated_value = max(values)
                elif aggregation_type == AggregationType.SUM:
                    aggregated_value = sum(values)
                elif aggregation_type == AggregationType.COUNT:
                    aggregated_value = len(values)
                elif aggregation_type == AggregationType.MEDIAN:
                    aggregated_value = statistics.median(values)
                elif aggregation_type == AggregationType.PERCENTILE_95:
                    aggregated_value = statistics.quantiles(values, n=20)[18]  # 95th percentile
                elif aggregation_type == AggregationType.PERCENTILE_99:
                    aggregated_value = statistics.quantiles(values, n=100)[98]  # 99th percentile
                elif aggregation_type == AggregationType.STANDARD_DEVIATION:
                    aggregated_value = statistics.stdev(values) if len(values) > 1 else 0
                else:
                    raise ValueError(f"Unsupported aggregation type: {aggregation_type}")

                # Store aggregation
                cursor.execute("""
                    INSERT INTO metric_aggregations (
                        aggregation_id, metric_type, category, aggregation_type,
                        time_period, start_time, end_time, value, sample_count, source_filter
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    aggregation_id, metric_type.value, category.value, aggregation_type.value,
                    time_period, start_time.isoformat(), end_time.isoformat(),
                    aggregated_value, len(values), source_filter
                ))

                conn.commit()
                conn.close()

                self._logger.info(f"Created aggregation {aggregation_id}: {aggregation_type.value} of {len(values)} {metric_type.value} metrics")
                return aggregation_id

            except Exception as e:
                self._logger.error(f"Failed to create aggregation: {e}")
                raise

    def get_aggregations(self, metric_type: Optional[MetricType] = None,
                        category: Optional[MetricCategory] = None,
                        aggregation_type: Optional[AggregationType] = None,
                        time_period: Optional[str] = None,
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None,
                        limit: int = 100) -> List[MetricAggregation]:
        """
        Retrieve metric aggregations with filtering options.

        Args:
            metric_type: Optional metric type filter
            category: Optional category filter
            aggregation_type: Optional aggregation type filter
            time_period: Optional time period filter
            start_time: Optional start time filter
            end_time: Optional end time filter
            limit: Maximum number of aggregations to return

        Returns:
            List of metric aggregations
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                query = "SELECT * FROM metric_aggregations WHERE 1=1"
                params = []

                if metric_type:
                    query += " AND metric_type = ?"
                    params.append(metric_type.value)

                if category:
                    query += " AND category = ?"
                    params.append(category.value)

                if aggregation_type:
                    query += " AND aggregation_type = ?"
                    params.append(aggregation_type.value)

                if time_period:
                    query += " AND time_period = ?"
                    params.append(time_period)

                if start_time:
                    query += " AND start_time >= ?"
                    params.append(start_time.isoformat())

                if end_time:
                    query += " AND end_time <= ?"
                    params.append(end_time.isoformat())

                query += " ORDER BY start_time DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                aggregations = []
                for row in rows:
                    aggregation = MetricAggregation(
                        aggregation_id=row[0],
                        metric_type=MetricType(row[1]),
                        category=MetricCategory(row[2]),
                        aggregation_type=AggregationType(row[3]),
                        time_period=row[4],
                        start_time=datetime.fromisoformat(row[5]),
                        end_time=datetime.fromisoformat(row[6]),
                        value=row[7],
                        sample_count=row[8],
                        source_filter=row[9]
                    )
                    aggregations.append(aggregation)

                return aggregations

            except Exception as e:
                self._logger.error(f"Failed to get aggregations: {e}")
                raise

    def set_metric_threshold(self, metric_type: MetricType, category: MetricCategory,
                           warning_threshold: Optional[float] = None,
                           critical_threshold: Optional[float] = None,
                           comparison_operator: str = 'GT',
                           source_pattern: Optional[str] = None) -> str:
        """
        Set a metric threshold for alerting.

        Args:
            metric_type: Type of metric
            category: Metric category
            warning_threshold: Optional warning threshold value
            critical_threshold: Optional critical threshold value
            comparison_operator: Comparison operator ('GT' or 'LT')
            source_pattern: Optional source pattern for filtering

        Returns:
            Threshold ID
        """
        threshold_id = str(uuid4())

        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO metric_thresholds (
                        threshold_id, metric_type, category, source_pattern,
                        warning_threshold, critical_threshold, comparison_operator
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    threshold_id, metric_type.value, category.value, source_pattern,
                    warning_threshold, critical_threshold, comparison_operator
                ))

                conn.commit()
                conn.close()

                self._logger.info(f"Set threshold {threshold_id} for {metric_type.value}: warning={warning_threshold}, critical={critical_threshold}")
                return threshold_id

            except Exception as e:
                self._logger.error(f"Failed to set metric threshold: {e}")
                raise

    def get_active_alerts(self, alert_level: Optional[str] = None,
                         acknowledged: Optional[bool] = None,
                         limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get active metric alerts.

        Args:
            alert_level: Optional alert level filter ('WARNING' or 'CRITICAL')
            acknowledged: Optional filter for acknowledged alerts
            limit: Maximum number of alerts to return

        Returns:
            List of alert dictionaries
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                query = "SELECT * FROM metric_alerts WHERE resolved_at IS NULL"
                params = []

                if alert_level:
                    query += " AND alert_level = ?"
                    params.append(alert_level)

                if acknowledged is not None:
                    query += " AND acknowledged = ?"
                    params.append(1 if acknowledged else 0)

                query += " ORDER BY triggered_at DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                alerts = []
                for row in rows:
                    alert = {
                        'alert_id': row[0],
                        'threshold_id': row[1],
                        'metric_id': row[2],
                        'alert_level': row[3],
                        'triggered_at': row[4],
                        'resolved_at': row[5],
                        'current_value': row[6],
                        'threshold_value': row[7],
                        'message': row[8],
                        'acknowledged': bool(row[9])
                    }
                    alerts.append(alert)

                return alerts

            except Exception as e:
                self._logger.error(f"Failed to get active alerts: {e}")
                raise

    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Acknowledge a metric alert.

        Args:
            alert_id: Alert ID to acknowledge

        Returns:
            True if acknowledgment was successful
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE metric_alerts
                    SET acknowledged = 1
                    WHERE alert_id = ?
                """, (alert_id,))

                updated = cursor.rowcount > 0
                conn.commit()
                conn.close()

                if updated:
                    self._logger.info(f"Acknowledged alert {alert_id}")

                return updated

            except Exception as e:
                self._logger.error(f"Failed to acknowledge alert: {e}")
                raise

    def resolve_alert(self, alert_id: str) -> bool:
        """
        Resolve a metric alert.

        Args:
            alert_id: Alert ID to resolve

        Returns:
            True if resolution was successful
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE metric_alerts
                    SET resolved_at = ?
                    WHERE alert_id = ?
                """, (datetime.now(timezone.utc).isoformat(), alert_id))

                updated = cursor.rowcount > 0
                conn.commit()
                conn.close()

                if updated:
                    self._logger.info(f"Resolved alert {alert_id}")

                return updated

            except Exception as e:
                self._logger.error(f"Failed to resolve alert: {e}")
                raise

    def get_performance_summary(self, start_time: Optional[datetime] = None,
                               end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get performance summary statistics.

        Args:
            start_time: Optional start time for summary
            end_time: Optional end time for summary

        Returns:
            Performance summary dictionary
        """
        if start_time is None:
            start_time = datetime.now(timezone.utc) - timedelta(hours=24)
        if end_time is None:
            end_time = datetime.now(timezone.utc)

        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Get metric counts by type
                cursor.execute("""
                    SELECT metric_type, COUNT(*) as count
                    FROM performance_metrics
                    WHERE timestamp >= ? AND timestamp <= ?
                    GROUP BY metric_type
                """, (start_time.isoformat(), end_time.isoformat()))
                metric_counts = {row[0]: row[1] for row in cursor.fetchall()}

                # Get metric counts by category
                cursor.execute("""
                    SELECT category, COUNT(*) as count
                    FROM performance_metrics
                    WHERE timestamp >= ? AND timestamp <= ?
                    GROUP BY category
                """, (start_time.isoformat(), end_time.isoformat()))
                category_counts = {row[0]: row[1] for row in cursor.fetchall()}

                # Get active alerts count
                cursor.execute("""
                    SELECT alert_level, COUNT(*) as count
                    FROM metric_alerts
                    WHERE resolved_at IS NULL
                    GROUP BY alert_level
                """)
                alert_counts = {row[0]: row[1] for row in cursor.fetchall()}

                # Get database size
                cursor.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                db_size_mb = (page_count * page_size) / (1024 * 1024)

                # Get total metrics count
                cursor.execute("""
                    SELECT COUNT(*) FROM performance_metrics
                    WHERE timestamp >= ? AND timestamp <= ?
                """, (start_time.isoformat(), end_time.isoformat()))
                total_metrics = cursor.fetchone()[0]

                conn.close()

                return {
                    'time_period': {
                        'start_time': start_time.isoformat(),
                        'end_time': end_time.isoformat()
                    },
                    'total_metrics': total_metrics,
                    'metric_counts_by_type': metric_counts,
                    'metric_counts_by_category': category_counts,
                    'active_alerts': alert_counts,
                    'database_size_mb': db_size_mb,
                    'retention_settings': {
                        'raw_retention_days': self._raw_retention_days,
                        'hourly_retention_days': self._hourly_retention_days,
                        'daily_retention_months': self._daily_retention_months,
                        'weekly_retention_years': self._weekly_retention_years
                    }
                }

            except Exception as e:
                self._logger.error(f"Failed to get performance summary: {e}")
                raise

    def cleanup_old_data(self) -> Dict[str, int]:
        """
        Clean up old data based on retention policies.

        Returns:
            Cleanup statistics
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Clean up old raw metrics
                raw_cutoff = datetime.now(timezone.utc) - timedelta(days=self._raw_retention_days)
                cursor.execute("""
                    DELETE FROM performance_metrics
                    WHERE timestamp < ?
                """, (raw_cutoff.isoformat(),))
                deleted_metrics = cursor.rowcount

                # Clean up old hourly aggregations
                hourly_cutoff = datetime.now(timezone.utc) - timedelta(days=self._hourly_retention_days)
                cursor.execute("""
                    DELETE FROM metric_aggregations
                    WHERE time_period LIKE '%h' AND start_time < ?
                """, (hourly_cutoff.isoformat(),))
                deleted_hourly = cursor.rowcount

                # Clean up old daily aggregations
                daily_cutoff = datetime.now(timezone.utc) - timedelta(days=self._daily_retention_months * 30)
                cursor.execute("""
                    DELETE FROM metric_aggregations
                    WHERE time_period LIKE '%d' AND start_time < ?
                """, (daily_cutoff.isoformat(),))
                deleted_daily = cursor.rowcount

                # Clean up old weekly aggregations
                weekly_cutoff = datetime.now(timezone.utc) - timedelta(days=self._weekly_retention_years * 365)
                cursor.execute("""
                    DELETE FROM metric_aggregations
                    WHERE time_period LIKE '%w' AND start_time < ?
                """, (weekly_cutoff.isoformat(),))
                deleted_weekly = cursor.rowcount

                # Clean up resolved alerts older than 30 days
                alert_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
                cursor.execute("""
                    DELETE FROM metric_alerts
                    WHERE resolved_at IS NOT NULL AND resolved_at < ?
                """, (alert_cutoff.isoformat(),))
                deleted_alerts = cursor.rowcount

                conn.commit()
                conn.close()

                stats = {
                    'deleted_metrics': deleted_metrics,
                    'deleted_hourly_aggregations': deleted_hourly,
                    'deleted_daily_aggregations': deleted_daily,
                    'deleted_weekly_aggregations': deleted_weekly,
                    'deleted_alerts': deleted_alerts
                }

                total_deleted = sum(stats.values())
                self._logger.info(f"Cleanup completed: {total_deleted} total records deleted")
                return stats

            except Exception as e:
                self._logger.error(f"Failed to cleanup old data: {e}")
                raise
