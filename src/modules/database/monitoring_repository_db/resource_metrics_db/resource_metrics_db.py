"""
Module: resource_metrics_db
Description: Stores system resource utilization data with circular buffer implementation for real-time monitoring
Phase: 4
Location: /src/modules/database/monitoring_repository_db/resource_metrics_db/
"""

# Standard library imports
import sqlite3
import threading
import time
import json
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from uuid import uuid4

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import get_logger


class MetricType(Enum):
    """Types of resource metrics."""
    CPU = "cpu"
    MEMORY = "memory"
    GPU = "gpu"
    DISK = "disk"
    NETWORK = "network"
    THERMAL = "thermal"


class AggregationPeriod(Enum):
    """Aggregation periods for metrics."""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"


@dataclass
class ResourceMetric:
    """Resource metric data structure."""
    metric_id: str
    metric_type: MetricType
    timestamp: datetime
    resource_name: str
    value: float
    unit: str
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'metric_id': self.metric_id,
            'metric_type': self.metric_type.value,
            'timestamp': self.timestamp.isoformat(),
            'resource_name': self.resource_name,
            'value': self.value,
            'unit': self.unit,
            'metadata': self.metadata
        }


@dataclass
class AggregatedMetric:
    """Aggregated metric data structure."""
    aggregation_id: str
    metric_type: MetricType
    resource_name: str
    period: AggregationPeriod
    start_time: datetime
    end_time: datetime
    min_value: float
    max_value: float
    avg_value: float
    sum_value: float
    count: int
    percentile_95: Optional[float] = None
    percentile_99: Optional[float] = None


class ResourceMetricsDB:
    """
    Resource metrics database manager.
    
    Handles storage and retrieval of system resource utilization data
    with circular buffer implementation for real-time monitoring and
    efficient time-series storage with automatic aggregation.
    """
    
    def __init__(self, db_path: Optional[str] = None, buffer_size: int = 10000):
        """
        Initialize the resource metrics database.
        
        Args:
            db_path: Path to the database file
            buffer_size: Size of in-memory circular buffer for real-time metrics
        """
        if db_path is None:
            # Default to monitoring data directory
            data_dir = Path.home() / ".mikrodok" / "data" / "monitoring"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "resource_metrics.db")
        
        self._db_path = db_path
        self._lock = threading.RLock()
        self._logger = get_logger(__name__)
        self._buffer_size = buffer_size
        
        # In-memory circular buffers for real-time access
        self._metric_buffers: Dict[MetricType, deque] = {
            metric_type: deque(maxlen=buffer_size) for metric_type in MetricType
        }
        
        # Retention settings
        self._raw_retention_hours = 24  # Keep raw metrics for 24 hours
        self._aggregated_retention_days = 90  # Keep aggregated metrics for 90 days
        
        self._initialize_database()
        self._start_cleanup_thread()
        
        self._logger.info(f"ResourceMetricsDB initialized with database: {self._db_path}")
    
    def _initialize_database(self) -> None:
        """Initialize database tables and indexes."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            # Enable WAL mode for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=10000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA foreign_keys=ON")
            
            # Create raw metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS resource_metrics (
                    metric_id TEXT PRIMARY KEY,
                    metric_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    resource_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create aggregated metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS aggregated_metrics (
                    aggregation_id TEXT PRIMARY KEY,
                    metric_type TEXT NOT NULL,
                    resource_name TEXT NOT NULL,
                    period TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    min_value REAL NOT NULL,
                    max_value REAL NOT NULL,
                    avg_value REAL NOT NULL,
                    sum_value REAL NOT NULL,
                    count INTEGER NOT NULL,
                    percentile_95 REAL,
                    percentile_99 REAL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for efficient queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_resource_metrics_type_time 
                ON resource_metrics(metric_type, timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_resource_metrics_resource_time 
                ON resource_metrics(resource_name, timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_aggregated_metrics_type_period 
                ON aggregated_metrics(metric_type, period, start_time)
            """)
            
            conn.commit()
            conn.close()
            
            self._logger.info("Resource metrics database initialized successfully")
            
        except Exception as e:
            self._logger.error(f"Failed to initialize resource metrics database: {e}")
            raise

    def _start_cleanup_thread(self) -> None:
        """Start background thread for data cleanup and aggregation."""
        def cleanup_worker():
            while True:
                try:
                    time.sleep(3600)  # Run every hour
                    self._cleanup_old_data()
                    self._aggregate_metrics()
                except Exception as e:
                    self._logger.error(f"Cleanup thread error: {e}")

        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        self._logger.info("Started cleanup and aggregation thread")

    def store_metric(self, metric_type: MetricType, resource_name: str,
                    value: float, unit: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Store a resource metric.

        Args:
            metric_type: Type of metric
            resource_name: Name of the resource
            value: Metric value
            unit: Unit of measurement
            metadata: Optional metadata

        Returns:
            Metric ID
        """
        metric_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)

        metric = ResourceMetric(
            metric_id=metric_id,
            metric_type=metric_type,
            timestamp=timestamp,
            resource_name=resource_name,
            value=value,
            unit=unit,
            metadata=metadata
        )

        # Add to circular buffer for real-time access
        self._metric_buffers[metric_type].append(metric)

        # Store in database
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO resource_metrics (
                        metric_id, metric_type, timestamp, resource_name,
                        value, unit, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    metric_id,
                    metric_type.value,
                    timestamp.isoformat(),
                    resource_name,
                    value,
                    unit,
                    json.dumps(metadata) if metadata else None
                ))

                conn.commit()
                conn.close()

                self._logger.debug(f"Stored metric: {metric_type.value}/{resource_name} = {value} {unit}")
                return metric_id

            except Exception as e:
                self._logger.error(f"Failed to store metric: {e}")
                raise

    def get_recent_metrics(self, metric_type: MetricType,
                          resource_name: Optional[str] = None,
                          limit: int = 100) -> List[ResourceMetric]:
        """
        Get recent metrics from circular buffer.

        Args:
            metric_type: Type of metric to retrieve
            resource_name: Optional resource name filter
            limit: Maximum number of metrics to return

        Returns:
            List of recent metrics
        """
        buffer = self._metric_buffers[metric_type]

        if resource_name:
            metrics = [m for m in buffer if m.resource_name == resource_name]
        else:
            metrics = list(buffer)

        # Return most recent metrics first
        return sorted(metrics, key=lambda m: m.timestamp, reverse=True)[:limit]

    def get_metrics_by_time_range(self, metric_type: MetricType,
                                 start_time: datetime, end_time: datetime,
                                 resource_name: Optional[str] = None) -> List[ResourceMetric]:
        """
        Get metrics within a time range from database.

        Args:
            metric_type: Type of metric to retrieve
            start_time: Start of time range
            end_time: End of time range
            resource_name: Optional resource name filter

        Returns:
            List of metrics in time range
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                query = """
                    SELECT metric_id, metric_type, timestamp, resource_name,
                           value, unit, metadata
                    FROM resource_metrics
                    WHERE metric_type = ? AND timestamp BETWEEN ? AND ?
                """
                params = [metric_type.value, start_time.isoformat(), end_time.isoformat()]

                if resource_name:
                    query += " AND resource_name = ?"
                    params.append(resource_name)

                query += " ORDER BY timestamp DESC"

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                metrics = []
                for row in rows:
                    metadata = json.loads(row[6]) if row[6] else None
                    metric = ResourceMetric(
                        metric_id=row[0],
                        metric_type=MetricType(row[1]),
                        timestamp=datetime.fromisoformat(row[2]),
                        resource_name=row[3],
                        value=row[4],
                        unit=row[5],
                        metadata=metadata
                    )
                    metrics.append(metric)

                return metrics

            except Exception as e:
                self._logger.error(f"Failed to get metrics by time range: {e}")
                raise

    def get_aggregated_metrics(self, metric_type: MetricType, period: AggregationPeriod,
                              start_time: datetime, end_time: datetime,
                              resource_name: Optional[str] = None) -> List[AggregatedMetric]:
        """
        Get aggregated metrics for a time period.

        Args:
            metric_type: Type of metric to retrieve
            period: Aggregation period
            start_time: Start of time range
            end_time: End of time range
            resource_name: Optional resource name filter

        Returns:
            List of aggregated metrics
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                query = """
                    SELECT aggregation_id, metric_type, resource_name, period,
                           start_time, end_time, min_value, max_value, avg_value,
                           sum_value, count, percentile_95, percentile_99
                    FROM aggregated_metrics
                    WHERE metric_type = ? AND period = ? AND start_time >= ? AND end_time <= ?
                """
                params = [metric_type.value, period.value, start_time.isoformat(), end_time.isoformat()]

                if resource_name:
                    query += " AND resource_name = ?"
                    params.append(resource_name)

                query += " ORDER BY start_time DESC"

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                aggregated_metrics = []
                for row in rows:
                    metric = AggregatedMetric(
                        aggregation_id=row[0],
                        metric_type=MetricType(row[1]),
                        resource_name=row[2],
                        period=AggregationPeriod(row[3]),
                        start_time=datetime.fromisoformat(row[4]),
                        end_time=datetime.fromisoformat(row[5]),
                        min_value=row[6],
                        max_value=row[7],
                        avg_value=row[8],
                        sum_value=row[9],
                        count=row[10],
                        percentile_95=row[11],
                        percentile_99=row[12]
                    )
                    aggregated_metrics.append(metric)

                return aggregated_metrics

            except Exception as e:
                self._logger.error(f"Failed to get aggregated metrics: {e}")
                raise

    def _aggregate_metrics(self) -> None:
        """Aggregate raw metrics into time-based summaries."""
        try:
            current_time = datetime.now(timezone.utc)

            # Aggregate by minute for the last hour
            self._aggregate_period(AggregationPeriod.MINUTE, current_time - timedelta(hours=1), current_time)

            # Aggregate by hour for the last day
            self._aggregate_period(AggregationPeriod.HOUR, current_time - timedelta(days=1), current_time)

            # Aggregate by day for the last week
            self._aggregate_period(AggregationPeriod.DAY, current_time - timedelta(weeks=1), current_time)

            self._logger.debug("Completed metric aggregation")

        except Exception as e:
            self._logger.error(f"Failed to aggregate metrics: {e}")

    def _aggregate_period(self, period: AggregationPeriod, start_time: datetime, end_time: datetime) -> None:
        """Aggregate metrics for a specific period."""
        with self._lock:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Get time bucket size
                if period == AggregationPeriod.MINUTE:
                    bucket_seconds = 60
                elif period == AggregationPeriod.HOUR:
                    bucket_seconds = 3600
                elif period == AggregationPeriod.DAY:
                    bucket_seconds = 86400
                else:  # WEEK
                    bucket_seconds = 604800

                # Aggregate metrics by type and resource
                for metric_type in MetricType:
                    cursor.execute("""
                        SELECT DISTINCT resource_name FROM resource_metrics
                        WHERE metric_type = ? AND timestamp BETWEEN ? AND ?
                    """, (metric_type.value, start_time.isoformat(), end_time.isoformat()))

                    resources = [row[0] for row in cursor.fetchall()]

                    for resource_name in resources:
                        self._aggregate_resource_metrics(
                            cursor, metric_type, resource_name, period,
                            start_time, end_time, bucket_seconds
                        )

                conn.commit()
                conn.close()

            except Exception as e:
                self._logger.error(f"Failed to aggregate period {period.value}: {e}")
                raise

    def _aggregate_resource_metrics(self, cursor: sqlite3.Cursor, metric_type: MetricType,
                                   resource_name: str, period: AggregationPeriod,
                                   start_time: datetime, end_time: datetime,
                                   bucket_seconds: int) -> None:
        """Aggregate metrics for a specific resource and time period."""
        # Calculate time buckets
        bucket_start = start_time

        while bucket_start < end_time:
            bucket_end = bucket_start + timedelta(seconds=bucket_seconds)
            if bucket_end > end_time:
                bucket_end = end_time

            # Check if aggregation already exists
            cursor.execute("""
                SELECT COUNT(*) FROM aggregated_metrics
                WHERE metric_type = ? AND resource_name = ? AND period = ?
                AND start_time = ? AND end_time = ?
            """, (
                metric_type.value, resource_name, period.value,
                bucket_start.isoformat(), bucket_end.isoformat()
            ))

            if cursor.fetchone()[0] > 0:
                bucket_start = bucket_end
                continue

            # Get raw metrics for this bucket
            cursor.execute("""
                SELECT value FROM resource_metrics
                WHERE metric_type = ? AND resource_name = ?
                AND timestamp >= ? AND timestamp < ?
                ORDER BY value
            """, (
                metric_type.value, resource_name,
                bucket_start.isoformat(), bucket_end.isoformat()
            ))

            values = [row[0] for row in cursor.fetchall()]

            if values:
                # Calculate aggregated statistics
                min_value = min(values)
                max_value = max(values)
                avg_value = sum(values) / len(values)
                sum_value = sum(values)
                count = len(values)

                # Calculate percentiles
                percentile_95 = self._calculate_percentile(values, 95)
                percentile_99 = self._calculate_percentile(values, 99)

                # Store aggregated metric
                aggregation_id = str(uuid4())
                cursor.execute("""
                    INSERT INTO aggregated_metrics (
                        aggregation_id, metric_type, resource_name, period,
                        start_time, end_time, min_value, max_value, avg_value,
                        sum_value, count, percentile_95, percentile_99
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    aggregation_id, metric_type.value, resource_name, period.value,
                    bucket_start.isoformat(), bucket_end.isoformat(),
                    min_value, max_value, avg_value, sum_value, count,
                    percentile_95, percentile_99
                ))

            bucket_start = bucket_end

    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value from sorted list."""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = (percentile / 100.0) * (len(sorted_values) - 1)

        if index.is_integer():
            return sorted_values[int(index)]
        else:
            lower_index = int(index)
            upper_index = lower_index + 1
            if upper_index >= len(sorted_values):
                return sorted_values[lower_index]

            weight = index - lower_index
            return sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight

    def _cleanup_old_data(self) -> None:
        """Clean up old metrics based on retention policies."""
        try:
            current_time = datetime.now(timezone.utc)

            # Clean up raw metrics older than retention period
            raw_cutoff = current_time - timedelta(hours=self._raw_retention_hours)

            # Clean up aggregated metrics older than retention period
            aggregated_cutoff = current_time - timedelta(days=self._aggregated_retention_days)

            with self._lock:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # Delete old raw metrics
                cursor.execute("""
                    DELETE FROM resource_metrics WHERE timestamp < ?
                """, (raw_cutoff.isoformat(),))
                raw_deleted = cursor.rowcount

                # Delete old aggregated metrics
                cursor.execute("""
                    DELETE FROM aggregated_metrics WHERE created_at < ?
                """, (aggregated_cutoff.isoformat(),))
                aggregated_deleted = cursor.rowcount

                conn.commit()
                conn.close()

                if raw_deleted > 0 or aggregated_deleted > 0:
                    self._logger.info(f"Cleaned up {raw_deleted} raw metrics and {aggregated_deleted} aggregated metrics")

        except Exception as e:
            self._logger.error(f"Failed to cleanup old data: {e}")

    def get_resource_summary(self, metric_type: MetricType,
                           resource_name: str, hours: int = 24) -> Dict[str, Any]:
        """
        Get summary statistics for a resource over the specified time period.

        Args:
            metric_type: Type of metric
            resource_name: Name of the resource
            hours: Number of hours to look back

        Returns:
            Dictionary with summary statistics
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        metrics = self.get_metrics_by_time_range(metric_type, start_time, end_time, resource_name)

        if not metrics:
            return {
                'resource_name': resource_name,
                'metric_type': metric_type.value,
                'period_hours': hours,
                'count': 0,
                'min_value': None,
                'max_value': None,
                'avg_value': None,
                'latest_value': None,
                'latest_timestamp': None
            }

        values = [m.value for m in metrics]

        return {
            'resource_name': resource_name,
            'metric_type': metric_type.value,
            'period_hours': hours,
            'count': len(values),
            'min_value': min(values),
            'max_value': max(values),
            'avg_value': sum(values) / len(values),
            'latest_value': metrics[0].value,  # metrics are sorted by timestamp desc
            'latest_timestamp': metrics[0].timestamp.isoformat()
        }

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        try:
            # Clear circular buffers
            for buffer in self._metric_buffers.values():
                buffer.clear()

            self._logger.info("ResourceMetricsDB closed successfully")

        except Exception as e:
            self._logger.error(f"Error closing ResourceMetricsDB: {e}")
